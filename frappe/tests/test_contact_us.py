from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.www.contact import (
	get_contact_message_context,
	get_contact_message_html,
	process_contact_message,
)


class TestContactMessage(FrappeTestCase):
	def test_context_escapes_guest_values(self):
		context = get_contact_message_context(
			"visitor@example.com",
			"<i>Quote</i>",
			"Need a <b>quote</b>",
			{"full_name": "<script>x</script>", "sender": "spoofed@example.com"},
		)

		self.assertEqual(context["sender"], "visitor@example.com")
		self.assertEqual(context["subject"], "&lt;i&gt;Quote&lt;/i&gt;")
		self.assertEqual(context["full_name"], "&lt;script&gt;x&lt;/script&gt;")
		self.assertEqual(context["message"], "Need a &lt;b&gt;quote&lt;/b&gt;")

	def test_context_without_args(self):
		context = get_contact_message_context("visitor@example.com", "Quote", "Hello")
		self.assertEqual(list(context), ["sender", "subject", "message"])

	def test_html_lines(self):
		context = get_contact_message_context(
			"visitor@example.com",
			"Quote",
			"First line\nSecond line",
			{"full_name": "Web Visitor", "organization": "", "employees": 25},
		)
		html = get_contact_message_html(context)

		self.assertIn("<b>Sender:</b> visitor@example.com", html)
		self.assertIn("<b>Full Name:</b> Web Visitor", html)
		self.assertIn("<b>Employees:</b> 25", html)
		self.assertNotIn("Organization", html)
		self.assertIn("<b>Message:</b> First line<br>Second line", html)
		self.assertTrue(html.endswith("Second line"))


class TestProcessContactMessage(FrappeTestCase):
	def setUp(self):
		self.settings = frappe.get_single("Contact Us Settings")
		self.original_settings = {
			fieldname: self.settings.get(fieldname)
			for fieldname in (
				"is_disabled",
				"forward_to_email",
				"send_acknowledgement_email",
				"confirmation_email_template",
			)
		}
		self.update_settings(
			is_disabled=0,
			forward_to_email="sales@example.com",
			send_acknowledgement_email=1,
			confirmation_email_template=None,
		)

	def tearDown(self):
		self.update_settings(**self.original_settings)

	def update_settings(self, **values):
		self.settings.update(values)
		self.settings.save()

	def get_communications(self, sender):
		return frappe.get_all("Communication", filters={"sender": sender}, pluck="content")

	@patch("frappe.sendmail")
	def test_forward_and_acknowledge(self, sendmail):
		process_contact_message(
			"visitor@example.com",
			"Need a <b>quote</b>",
			subject="Quote",
			args='{"full_name": "Web Visitor"}',
		)

		forward, acknowledgement = (call.kwargs for call in sendmail.call_args_list)
		self.assertEqual(forward["recipients"], "sales@example.com")
		self.assertEqual(forward["reply_to"], "visitor@example.com")
		self.assertEqual(forward["subject"], "Quote")
		self.assertIn("<b>Full Name:</b> Web Visitor", forward["content"])
		self.assertIn("Need a &lt;b&gt;quote&lt;/b&gt;", forward["content"])

		# the default reply doesn't quote the guest's message
		self.assertEqual(acknowledgement["recipients"], "visitor@example.com")
		self.assertNotIn("quote", acknowledgement["content"])

		self.assertEqual(self.get_communications("visitor@example.com"), ["Need a &lt;b&gt;quote&lt;/b&gt;"])

	@patch("frappe.sendmail")
	def test_confirmation_email_template(self, sendmail):
		email_template = frappe.get_doc(
			doctype="Email Template",
			name="_Test Contact Confirmation",
			subject="Thanks {{ full_name }}",
			response="We got your message: {{ message }}",
		).insert(ignore_if_duplicate=True)
		self.update_settings(forward_to_email=None, confirmation_email_template=email_template.name)

		process_contact_message(
			"visitor@example.com",
			"<i>Hi</i>",
			args={"full_name": "<b>Web Visitor</b>"},
			create_communication=0,
		)

		acknowledgement = sendmail.call_args.kwargs
		self.assertEqual(acknowledgement["subject"], "Thanks &lt;b&gt;Web Visitor&lt;/b&gt;")
		self.assertEqual(acknowledgement["content"], "We got your message: &lt;i&gt;Hi&lt;/i&gt;")
		self.assertFalse(self.get_communications("visitor@example.com"))

	@patch("frappe.sendmail")
	def test_disabled_and_invalid_sender(self, sendmail):
		self.assertRaises(frappe.ValidationError, process_contact_message, "", "Hello")
		self.assertRaises(frappe.InvalidEmailAddressError, process_contact_message, "not an email", "Hello")

		self.update_settings(is_disabled=1)
		process_contact_message("visitor@example.com", "Hello")
		sendmail.assert_not_called()
		self.assertFalse(self.get_communications("visitor@example.com"))
