from frappe.tests.utils import FrappeTestCase
from frappe.www.contact import get_contact_message_context, get_contact_message_html


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
