# Copyright (c) 2023, Frappe Technologies and Contributors
# See license.txt

import frappe
from frappe.core.doctype.notification_count.notification_count import (
	add_notification_count,
	clear_notification_count,
	get_all_notification_count,
	get_notification_count,
	get_notification_last_scheduled,
	set_notification_last_scheduled,
)
from frappe.tests.utils import FrappeTestCase
from frappe.utils import get_datetime


class TestNotificationCount(FrappeTestCase):
	def setUp(self):
		self.todo = frappe.get_doc(doctype="ToDo", description="Test notification count").insert()

	def test_count_per_key_and_medium(self):
		add_notification_count("ToDo", self.todo.name, "_Test Key", "Email")
		add_notification_count("ToDo", self.todo.name, "_Test Key", "Email", count=2)
		add_notification_count("ToDo", self.todo.name, "_Test Key", "SMS")

		self.assertEqual(get_notification_count("ToDo", self.todo.name, "_Test Key", "Email"), 3)
		self.assertEqual(get_notification_count("ToDo", self.todo.name, "_Test Key", "SMS"), 1)
		self.assertEqual(get_notification_count("ToDo", self.todo.name, "_Test Other Key", "Email"), 0)

		count_doc = frappe.get_doc(
			"Notification Count",
			{"reference_doctype": "ToDo", "reference_name": self.todo.name, "notification_medium": "SMS"},
		)
		self.assertTrue(count_doc.last_sent_dt)

	def test_count_per_child_row(self):
		add_notification_count("ToDo", self.todo.name, "_Test Key", "Email")
		add_notification_count(
			"ToDo", self.todo.name, "_Test Key", "Email", child_doctype="Has Role", child_name="_Test Row 1"
		)

		self.assertEqual(
			get_notification_count(
				"ToDo",
				self.todo.name,
				"_Test Key",
				"Email",
				child_doctype="Has Role",
				child_name="_Test Row 1",
			),
			1,
		)
		self.assertEqual(
			get_notification_count(
				"ToDo",
				self.todo.name,
				"_Test Key",
				"Email",
				child_doctype="Has Role",
				child_name="_Test Row 2",
			),
			0,
		)

	def test_last_scheduled(self):
		self.assertIsNone(get_notification_last_scheduled("ToDo", self.todo.name, "_Test Key", "Email"))

		set_notification_last_scheduled(
			"ToDo", self.todo.name, "_Test Key", "Email", now_dt="2026-01-02 10:30:00"
		)

		self.assertEqual(
			get_notification_last_scheduled("ToDo", self.todo.name, "_Test Key", "Email"),
			get_datetime("2026-01-02 10:30:00"),
		)
		self.assertIsNone(get_notification_last_scheduled("ToDo", self.todo.name, "_Test Key", "SMS"))
		# scheduling doesn't count as sent
		self.assertEqual(get_notification_count("ToDo", self.todo.name, "_Test Key", "Email"), 0)

	def test_get_all_and_clear(self):
		add_notification_count("ToDo", self.todo.name, "_Test Key", "Email")
		add_notification_count("ToDo", self.todo.name, "_Test Key", "SMS", count=2)
		add_notification_count(
			"ToDo", self.todo.name, "_Test Key", "Email", child_doctype="Has Role", child_name="_Test Row 1"
		)

		all_counts = get_all_notification_count("ToDo", self.todo.name)
		self.assertEqual(
			[(d.notification_key, d.notification_medium, d.notification_count) for d in all_counts],
			[("_Test Key", "Email", 1), ("_Test Key", "SMS", 2), ("_Test Key", "Email", 1)],
		)
		self.assertEqual(
			len(get_all_notification_count("ToDo", self.todo.name, "Has Role", "_Test Row 1")), 1
		)
		self.assertEqual(get_all_notification_count(None, self.todo.name), [])

		# clearing a child row keeps the document's counts
		clear_notification_count("ToDo", self.todo.name, "Has Role", "_Test Row 1")
		self.assertEqual(len(get_all_notification_count("ToDo", self.todo.name)), 2)

		clear_notification_count("ToDo", self.todo.name)
		self.assertEqual(get_all_notification_count("ToDo", self.todo.name), [])
