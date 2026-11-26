# Copyright (c) 2022, Frappe Technologies and Contributors
# See license.txt

import frappe
from frappe.core.doctype.sms_template.sms_template import (
	get_sms_defaults,
	get_sms_template,
	get_sms_template_message,
)
from frappe.tests.utils import FrappeTestCase


class TestSMSTemplate(FrappeTestCase):
	def make_template(self, message, notification_key=None, enabled=1):
		return frappe.get_doc(
			doctype="SMS Template",
			reference_doctype="ToDo",
			notification_key=notification_key,
			message=message,
			enabled=enabled,
		).insert()

	def test_name_and_lookup_by_key(self):
		default = self.make_template("Default for {{ doc.description }}")
		keyed = self.make_template("Reminder for {{ doc.description }}", notification_key="_Test Reminder")
		self.make_template("Disabled", notification_key="_Test Disabled", enabled=0)

		self.assertEqual(default.name, "ToDo")
		self.assertEqual(keyed.name, "ToDo-_Test Reminder")

		self.assertEqual(get_sms_template("ToDo").name, "ToDo")
		self.assertEqual(get_sms_template("ToDo", "_Test Reminder").name, "ToDo-_Test Reminder")
		self.assertIsNone(get_sms_template("ToDo", "_Test Disabled"))
		self.assertIsNone(get_sms_template("ToDo", "_Test No Such Key"))

		todo = frappe.get_doc(doctype="ToDo", description="Test template").insert()
		self.assertEqual(get_sms_template_message("_Test Reminder", todo), "Reminder for Test template")
		self.assertEqual(get_sms_template_message("_Test No Such Key", todo), "")
		# the document replaces a doc in the given context
		self.assertEqual(
			get_sms_template_message("_Test Reminder", todo, context={"doc": {"description": "Other"}}),
			"Reminder for Test template",
		)

	def test_get_sms_defaults(self):
		self.make_template("Hello {{ doc.description }}", notification_key="_Test Greeting")
		todo = frappe.get_doc(doctype="ToDo", description="Test defaults").insert()
		contact = frappe.get_doc(
			doctype="Contact",
			first_name="_Test SMS Template Contact",
			mobile_no="+971501234567",
			links=[{"link_doctype": "User", "link_name": "test@example.com"}],
		).insert()

		self.assertEqual(
			get_sms_defaults("ToDo", todo.name, "_Test Greeting", contact=contact.name),
			{"mobile_no": "+971501234567", "message": "Hello Test defaults"},
		)
		self.assertEqual(
			get_sms_defaults(
				"ToDo", todo.name, "_Test Greeting", party_doctype="User", party="test@example.com"
			),
			{"mobile_no": "+971501234567", "message": "Hello Test defaults"},
		)
		# a number that's given wins, no template means no message
		self.assertEqual(
			get_sms_defaults(
				"ToDo", todo.name, "_Test No Template", contact=contact.name, mobile_no="+971501234568"
			),
			{"mobile_no": "+971501234568", "message": ""},
		)
