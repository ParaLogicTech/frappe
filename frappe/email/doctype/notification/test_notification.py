# Copyright (c) 2018, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import json
from contextlib import contextmanager
from unittest.mock import patch

import frappe
import frappe.utils
from frappe.desk.form import assign_to
from frappe.tests.utils import FrappeTestCase

from .notification import get_comments_for_context

test_dependencies = ["User", "Notification"]


@contextmanager
def get_test_notification(config):
	try:
		notification = frappe.get_doc(doctype="Notification", **config).insert()
		yield notification
	finally:
		notification.delete()


@contextmanager
def doc_hook(doctype, method, handler):
	"""Hook `handler` (a dotted path) into `method` of `doctype`, as `doc_events` in hooks.py would"""
	doc_hooks = frappe.get_doc_hooks()
	doctype_hooks = dict(doc_hooks.get(doctype, {}))
	doctype_hooks[method] = [handler]
	with patch.dict(doc_hooks, {doctype: doctype_hooks}):
		yield


def skip_notification_hook(doc, method, notification_key=None, **kwargs):
	if notification_key == "_Test Validated Key" and "_Test Skip" in (doc.description or ""):
		return 0


def notification_attachment_hook(doc, method, notification_key=None):
	if notification_key == "_Test Attachment Key":
		return [{"file_url": "/files/_test_hooked_attachment.txt"}]


@contextmanager
def get_test_doctype_with_attach_field(doctype_name="Test Attach Doctype"):
	"""Create a temporary doctype with an attach field for testing."""
	try:
		# Create custom doctype with attach field
		if not frappe.db.exists("DocType", doctype_name):
			frappe.get_doc(
				{
					"doctype": "DocType",
					"name": doctype_name,
					"module": "Core",
					"custom": 1,
					"fields": [
						{"label": "Title", "fieldname": "title", "fieldtype": "Data", "reqd": 1},
						{"label": "Attachment", "fieldname": "attachment", "fieldtype": "Attach"},
					],
					"permissions": [
						{"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1}
					],
				}
			).insert()

		yield doctype_name

	finally:
		frappe.db.delete(doctype_name)
		frappe.delete_doc_if_exists("DocType", doctype_name, force=1)
		frappe.db.commit()


@contextmanager
def create_test_file(file_name="test_attachment.txt", content="Test file content"):
	"""Create a test file and return its File document."""
	try:
		file_doc = frappe.get_doc(
			{"doctype": "File", "file_name": file_name, "content": content, "is_private": 0}
		).insert()

		yield file_doc

	finally:
		frappe.delete_doc_if_exists("File", file_doc.name, force=1)
		frappe.db.commit()


class TestNotification(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("Email Queue")
		frappe.set_user("test@example.com")

		if not frappe.db.exists("Notification", {"name": "ToDo Status Update"}, "name"):
			notification = frappe.new_doc("Notification")
			notification.name = "ToDo Status Update"
			notification.subject = "ToDo Status Update"
			notification.document_type = "ToDo"
			notification.event = "Value Change"
			notification.value_changed = "status"
			notification.send_to_all_assignees = 1
			notification.set_property_after_alert = "description"
			notification.property_value = "Changed by Notification"
			notification.save()

		if not frappe.db.exists("Notification", {"name": "Contact Status Update"}, "name"):
			notification = frappe.new_doc("Notification")
			notification.name = "Contact Status Update"
			notification.subject = "Contact Status Update"
			notification.document_type = "Contact"
			notification.event = "Value Change"
			notification.value_changed = "status"
			notification.message = "Test Contact Update"
			notification.append("recipients", {"receiver_by_document_field": "email_id,email_ids"})
			notification.save()

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_new_and_save(self):
		"""Check creating a new communication triggers a notification."""
		communication = frappe.new_doc("Communication")
		communication.communication_type = "Comment"
		communication.subject = "test"
		communication.content = "test"
		communication.insert(ignore_permissions=True)

		self.assertTrue(
			frappe.db.get_value(
				"Email Queue",
				{
					"reference_doctype": "Communication",
					"reference_name": communication.name,
					"status": "Not Sent",
				},
			)
		)
		frappe.db.delete("Email Queue")

		communication.reload()
		communication.content = "test 2"
		communication.save()

		self.assertTrue(
			frappe.db.get_value(
				"Email Queue",
				{
					"reference_doctype": "Communication",
					"reference_name": communication.name,
					"status": "Not Sent",
				},
			)
		)

		self.assertEqual(frappe.db.get_value("Communication", communication.name, "subject"), "__testing__")

	def test_comments_in_context(self):
		todo = frappe.get_doc(doctype="ToDo", description="comments context").insert()
		self.assertIsNone(get_comments_for_context(todo))

		comment = todo.add_comment("Comment", "hello")
		email = frappe.get_doc(
			doctype="Communication",
			content="reply",
			sender="a@example.com",
			reference_doctype="ToDo",
			reference_name=todo.name,
		).insert()
		self.assertEqual(
			get_comments_for_context(todo),
			[
				{"comment": "hello", "by": comment.comment_email, "name": comment.name},
				{"comment": "reply", "by": "a@example.com", "name": email.name},
			],
		)

		todo.add_comment("Comment", "x" * 150)
		self.assertEqual(get_comments_for_context(todo)[-1]["comment"], "x" * 97 + "...")

	def test_condition(self):
		"""Check notification is triggered based on a condition."""
		event = frappe.new_doc("Event")
		event.subject = "test"
		event.event_type = "Private"
		event.starts_on = "2014-06-06 12:00:00"
		event.insert()

		self.assertFalse(
			frappe.db.get_value(
				"Email Queue",
				{"reference_doctype": "Event", "reference_name": event.name, "status": "Not Sent"},
			)
		)

		event.event_type = "Public"
		event.save()

		self.assertTrue(
			frappe.db.get_value(
				"Email Queue",
				{"reference_doctype": "Event", "reference_name": event.name, "status": "Not Sent"},
			)
		)

		# Make sure that we track the triggered notifications in communication doctype.
		self.assertTrue(
			frappe.db.get_value(
				"Communication",
				{
					"reference_doctype": "Event",
					"reference_name": event.name,
					"communication_type": "Automated Message",
				},
			)
		)

	def test_invalid_condition(self):
		frappe.set_user("Administrator")
		notification = frappe.new_doc("Notification")
		notification.subject = "test"
		notification.document_type = "ToDo"
		notification.send_alert_on = "New"
		notification.message = "test"

		recipent = frappe.new_doc("Notification Recipient")
		recipent.receiver_by_document_field = "owner"

		notification.recipents = recipent
		notification.condition = "test"

		self.assertRaises(frappe.ValidationError, notification.save)
		notification.delete()

	def test_value_changed(self):
		event = frappe.new_doc("Event")
		event.subject = "test"
		event.event_type = "Private"
		event.starts_on = "2014-06-06 12:00:00"
		event.insert()

		self.assertFalse(
			frappe.db.get_value(
				"Email Queue",
				{"reference_doctype": "Event", "reference_name": event.name, "status": "Not Sent"},
			)
		)

		event.subject = "test 1"
		event.save()

		self.assertFalse(
			frappe.db.get_value(
				"Email Queue",
				{"reference_doctype": "Event", "reference_name": event.name, "status": "Not Sent"},
			)
		)

		event.description = "test"
		event.save()

		self.assertTrue(
			frappe.db.get_value(
				"Email Queue",
				{"reference_doctype": "Event", "reference_name": event.name, "status": "Not Sent"},
			)
		)

	def test_system_notification_sets_app_from_module(self):
		"""A System Notification rule records its owning app (from `module`) on the log."""
		notification = {
			"name": "Test App From Module",
			"notification_title": "Test App From Module",
			"document_type": "Event",
			"module": "Core",  # owned by the frappe app
			"event": "New",
			"channel": "System Notification",
			"notification_type": "Alert",
			"recipients": [{"receiver_by_document_field": "owner"}],
		}

		with get_test_notification(notification) as n:
			frappe.db.delete("Notification Log", {"title": n.notification_title})

			event = frappe.new_doc("Event")
			event.subject = "Test App From Module Event"
			event.event_type = "Private"
			event.starts_on = frappe.utils.add_to_date(frappe.utils.now_datetime(), minutes=14)
			event.insert()

			app = frappe.db.get_value("Notification Log", {"title": n.notification_title}, "app")
			self.assertEqual(app, "frappe")

	def test_alert_disabled_on_wrong_field(self):
		frappe.set_user("Administrator")
		notification = frappe.get_doc(
			{
				"doctype": "Notification",
				"subject": "_Test Notification for wrong field",
				"document_type": "Event",
				"event": "Value Change",
				"attach_print": 0,
				"value_changed": "description1",
				"message": "Description changed",
				"recipients": [{"receiver_by_document_field": "owner"}],
			}
		).insert()
		frappe.db.commit()

		event = frappe.new_doc("Event")
		event.subject = "test-2"
		event.event_type = "Private"
		event.starts_on = "2014-06-06 12:00:00"
		event.insert()
		event.subject = "test 1"
		event.save()

		# verify that notification is disabled
		notification.reload()
		self.assertEqual(notification.enabled, 0)
		notification.delete()
		event.delete()

	def test_notification_key(self):
		from frappe.core.doctype.notification_count.notification_count import (
			get_notification_count,
			get_notification_last_scheduled,
		)
		from frappe.email.doctype.notification.notification import has_notification
		from frappe.email.queue import flush

		config = {
			"name": "_Test Notification Key",
			"subject": "_Test Notification Key",
			"document_type": "ToDo",
			"event": "New",
			"channel": "Email",
			"message": "Test notification key",
			"notification_key": "_Test Key",
			"recipients": [{"receiver_by_document_field": "owner"}],
		}
		with get_test_notification(config) as notification:
			self.assertEqual(notification.get_notification_key(), "_Test Key")
			self.assertTrue(has_notification("ToDo", "_Test Key"))
			self.assertFalse(has_notification("ToDo", "_Test Other Key"))

			todo = frappe.get_doc(doctype="ToDo", description="Test notification key").insert()

			email_keys = frappe.get_all(
				"Email Queue",
				filters={"reference_doctype": "ToDo", "reference_name": todo.name},
				pluck="notification_key",
			)
			self.assertEqual(email_keys, ["_Test Key"])
			self.assertTrue(get_notification_last_scheduled("ToDo", todo.name, "_Test Key", "Email"))

			# sending commits, which would keep this test's notification on the site
			with patch.object(frappe.db, "commit"):
				flush()
			self.assertEqual(get_notification_count("ToDo", todo.name, "_Test Key", "Email"), 1)

	def test_notification_key_defaults_to_name(self):
		config = {
			"name": "_Test Notification Without Key",
			"subject": "_Test Notification Without Key",
			"document_type": "ToDo",
			"event": "New",
			"channel": "Email",
			"message": "Test notification without key",
			"recipients": [{"receiver_by_document_field": "owner"}],
		}
		with get_test_notification(config) as notification:
			self.assertEqual(notification.get_notification_key(), "_Test Notification Without Key")

	def test_date_changed(self):
		event = frappe.new_doc("Event")
		event.subject = "test"
		event.event_type = "Private"
		event.starts_on = "2014-01-01 12:00:00"
		event.insert()

		self.assertFalse(
			frappe.db.get_value(
				"Email Queue",
				{"reference_doctype": "Event", "reference_name": event.name, "status": "Not Sent"},
			)
		)

		frappe.set_user("Administrator")
		frappe.get_doc(
			"Scheduled Job Type",
			dict(method="frappe.email.doctype.notification.notification.trigger_daily_alerts"),
		).execute()

		# not today, so no alert
		self.assertFalse(
			frappe.db.get_value(
				"Email Queue",
				{"reference_doctype": "Event", "reference_name": event.name, "status": "Not Sent"},
			)
		)

		event.starts_on = frappe.utils.add_days(frappe.utils.nowdate(), 2) + " 12:00:00"
		event.save()

		# Value Change notification alert will be trigger as description is not changed
		# mail will not be sent
		self.assertFalse(
			frappe.db.get_value(
				"Email Queue",
				{"reference_doctype": "Event", "reference_name": event.name, "status": "Not Sent"},
			)
		)

		frappe.get_doc(
			"Scheduled Job Type",
			dict(method="frappe.email.doctype.notification.notification.trigger_daily_alerts"),
		).execute()

		# today so show alert
		self.assertTrue(
			frappe.db.get_value(
				"Email Queue",
				{"reference_doctype": "Event", "reference_name": event.name, "status": "Not Sent"},
			)
		)

	def test_cc_jinja(self):
		frappe.db.delete("User", {"email": "test_jinja@example.com"})
		frappe.db.delete("Email Queue")
		frappe.db.delete("Email Queue Recipient")

		test_user = frappe.new_doc("User")
		test_user.name = "test_jinja"
		test_user.first_name = "test_jinja"
		test_user.email = "test_jinja@example.com"

		test_user.insert(ignore_permissions=True)

		self.assertTrue(
			frappe.db.get_value(
				"Email Queue",
				{"reference_doctype": "User", "reference_name": test_user.name, "status": "Not Sent"},
			)
		)

		self.assertTrue(frappe.db.get_value("Email Queue Recipient", {"recipient": "test_jinja@example.com"}))

		frappe.db.delete("User", {"email": "test_jinja@example.com"})
		frappe.db.delete("Email Queue")
		frappe.db.delete("Email Queue Recipient")

	def test_notification_to_assignee(self):
		todo = frappe.new_doc("ToDo")
		todo.description = "Test Notification"
		todo.save()

		assign_to.add(
			{
				"assign_to": ["test2@example.com"],
				"doctype": todo.doctype,
				"name": todo.name,
				"description": "Close this Todo",
			}
		)

		assign_to.add(
			{
				"assign_to": ["test1@example.com"],
				"doctype": todo.doctype,
				"name": todo.name,
				"description": "Close this Todo",
			}
		)

		# change status of todo
		todo.status = "Closed"
		todo.save()

		email_queue = frappe.get_doc(
			"Email Queue", {"reference_doctype": "ToDo", "reference_name": todo.name}
		)

		self.assertTrue(email_queue)

		# check if description is changed after alert since set_property_after_alert is set
		self.assertEqual(todo.description, "Changed by Notification")

		recipients = [d.recipient for d in email_queue.recipients]
		self.assertTrue("test2@example.com" in recipients)
		self.assertTrue("test1@example.com" in recipients)

	def test_notification_by_child_table_field(self):
		contact = frappe.new_doc("Contact")
		contact.first_name = "John Doe"
		contact.status = "Open"
		contact.append("email_ids", {"email_id": "test2@example.com", "is_primary": 1})

		contact.append("email_ids", {"email_id": "test1@example.com"})

		contact.save()

		# change status of contact
		contact.status = "Replied"
		contact.save()

		email_queue = frappe.get_doc(
			"Email Queue", {"reference_doctype": "Contact", "reference_name": contact.name}
		)

		self.assertTrue(email_queue)

		recipients = [d.recipient for d in email_queue.recipients]
		self.assertTrue("test2@example.com" in recipients)
		self.assertTrue("test1@example.com" in recipients)

	def test_notification_value_change_casted_types(self):
		"""Make sure value change event dont fire because of incorrect type comparisons."""
		frappe.set_user("Administrator")

		notification = {
			"document_type": "User",
			"subject": "User changed birthdate",
			"event": "Value Change",
			"channel": "System Notification",
			"value_changed": "birth_date",
			"recipients": [{"receiver_by_document_field": "email"}],
		}

		with get_test_notification(notification) as n:
			frappe.db.delete("Notification Log", {"subject": n.subject})

			user = frappe.get_doc("User", "test@example.com")
			user.birth_date = frappe.utils.add_days(user.birth_date, 1)
			user.save()

			user.reload()
			user.birth_date = frappe.utils.getdate(user.birth_date)
			user.save()
			self.assertEqual(1, frappe.db.count("Notification Log", {"subject": n.subject}))

	def test_attach_files_from_field(self):
		"""Test notification with 'From Field' attachment option."""
		frappe.db.delete("Email Queue")

		with get_test_doctype_with_attach_field("Test From Field Doctype") as test_doctype:
			with create_test_file("from_field_test.txt", "Content from specific field") as test_file:
				# Create notification with "From Field" attachment
				notification_config = {
					"name": "Test From Field Attachment",
					"subject": "Test From Field Attachment",
					"document_type": test_doctype,
					"event": "Save",
					"message": "Document saved with attachment",
					"channel": "Email",
					"attach_files": "From Field",
					"from_attach_field": "attachment",
					"recipients": [{"receiver_by_document_field": "owner"}],
				}

				with get_test_notification(notification_config):
					# Create document with attachment
					test_doc = frappe.get_doc(
						{
							"doctype": test_doctype,
							"title": "Test Document with Attachment",
							"attachment": test_file.file_url,
						}
					).insert()

					# Trigger save event to send notification
					test_doc.save()

					# Verify Email Queue created
					email_queue = frappe.get_doc(
						"Email Queue", {"reference_doctype": test_doctype, "reference_name": test_doc.name}
					)

					self.assertTrue(email_queue, "Email Queue not created")

					# Verify attachment metadata in Email Queue
					attachments = json.loads(email_queue.attachments) if email_queue.attachments else []
					self.assertEqual(len(attachments), 1, "Expected exactly one attachment")
					self.assertEqual(
						attachments[0].get("file_url"), test_file.file_url, "Attachment URL doesn't match"
					)

					# Clean up test document
					test_doc.delete()

	def test_attach_files_all(self):
		"""Test notification with 'All' attachment option."""
		frappe.db.delete("Email Queue")

		with get_test_doctype_with_attach_field("Test All Attachments Doctype") as test_doctype:
			with create_test_file("all_test_1.txt", "First file content") as test_file1:
				# Create notification with "All" attachment option
				notification_config = {
					"name": "Test All Attachments",
					"subject": "Test All Attachments",
					"document_type": test_doctype,
					"event": "Save",
					"message": "Document saved with all attachments",
					"channel": "Email",
					"attach_files": "All",
					"recipients": [{"receiver_by_document_field": "owner"}],
				}

				with get_test_notification(notification_config):
					# Create document with one attachment
					test_doc = frappe.get_doc(
						{
							"doctype": test_doctype,
							"title": "Test Document with Multiple Attachments",
							"attachment": test_file1.file_url,
						}
					).insert()

					# Upload additional file that is not attached to a specific field
					with create_test_file(
						"additional_file.txt", "Additional file content"
					) as additional_file:
						additional_file.attached_to_doctype = test_doctype
						additional_file.attached_to_name = test_doc.name
						additional_file.save()

						# Trigger save event to send notification
						test_doc.save()

						# Verify Email Queue created
						email_queue = frappe.get_doc(
							"Email Queue",
							{"reference_doctype": test_doctype, "reference_name": test_doc.name},
						)

						self.assertTrue(email_queue, "Email Queue not created")

						# Verify all attachments in Email Queue
						attachments = json.loads(email_queue.attachments) if email_queue.attachments else []

						# Should have the additional file that's directly attached to the document
						self.assertEqual(len(attachments), 2, "Expected exactly two attachments")

						# Verify the additional file is included
						attachment_urls = [att.get("file_url") for att in attachments]
						self.assertIn(
							test_file1.file_url, attachment_urls, "First file not found in attachments"
						)
						self.assertIn(
							additional_file.file_url,
							attachment_urls,
							"Additional file not found in attachments",
						)

					test_doc.delete()

	def test_attach_files_empty_option(self):
		"""Test notification with empty attachment option (no attachments)."""
		frappe.db.delete("Email Queue")

		# Create notification with empty attach_files option
		notification_config = {
			"name": "Test No Attachments",
			"subject": "Test No Attachments",
			"document_type": "ToDo",
			"event": "Save",
			"message": "Todo saved without attachments",
			"channel": "Email",
			"attach_print": 0,
			"attach_files": "",  # Empty option
			"recipients": [{"receiver_by_document_field": "owner"}],
		}

		with get_test_notification(notification_config):
			# Create a ToDo
			todo = frappe.new_doc("ToDo")
			todo.description = "Test ToDo"
			todo.insert()
			todo.save()

			# Verify Email Queue created
			email_queue = frappe.get_doc(
				"Email Queue", {"reference_doctype": "ToDo", "reference_name": todo.name}
			)

			self.assertTrue(email_queue, "Email Queue not created")

			# Verify no attachments in Email Queue (or empty list)
			attachments = json.loads(email_queue.attachments) if email_queue.attachments else []
			self.assertEqual(len(attachments), 0, "Expected no attachments")

			# Clean up
			todo.delete(ignore_permissions=True)

	def get_email_queue_for(self, doctype, name):
		return frappe.get_all(
			"Email Queue",
			filters={"reference_doctype": doctype, "reference_name": name},
			fields=["name", "attachments", "notification_key"],
		)

	def get_communications_for(self, doctype, name):
		return frappe.get_all(
			"Communication",
			filters={"reference_doctype": doctype, "reference_name": name},
			fields=["name", "subject", "content", "communication_medium", "communication_type"],
			order_by="creation",
		)

	def test_validate_notification_hook(self):
		config = {
			"name": "_Test Validated Notification",
			"subject": "_Test Validated Notification",
			"document_type": "ToDo",
			"event": "New",
			"channel": "Email",
			"message": "Test validated notification",
			"notification_key": "_Test Validated Key",
			"recipients": [{"receiver_by_document_field": "owner"}],
		}
		handler = "frappe.email.doctype.notification.test_notification.skip_notification_hook"
		with get_test_notification(config), doc_hook("ToDo", "validate_notification", handler):
			skipped = frappe.get_doc(doctype="ToDo", description="_Test Skip this one").insert()
			sent = frappe.get_doc(doctype="ToDo", description="_Test Send this one").insert()

			self.assertFalse(self.get_email_queue_for("ToDo", skipped.name))
			self.assertTrue(self.get_email_queue_for("ToDo", sent.name))

	def test_notification_attachment_hook(self):
		config = {
			"name": "_Test Hooked Attachment",
			"subject": "_Test Hooked Attachment",
			"document_type": "ToDo",
			"event": "New",
			"channel": "Email",
			"message": "Test hooked attachment",
			"notification_key": "_Test Attachment Key",
			"attach_files": "All",
			"recipients": [{"receiver_by_document_field": "owner"}],
		}
		handler = "frappe.email.doctype.notification.test_notification.notification_attachment_hook"
		with (
			get_test_notification(config) as notification,
			doc_hook("ToDo", "get_notification_attachment", handler),
		):
			todo = frappe.get_doc(doctype="ToDo", description="Test hooked attachment").insert()

			email_queue = self.get_email_queue_for("ToDo", todo.name)
			self.assertEqual(
				json.loads(email_queue[0].attachments), [{"file_url": "/files/_test_hooked_attachment.txt"}]
			)

			# without a value from the hook, the notification's own attachment settings apply
			notification.db_set("notification_key", "_Test Other Key")
			self.assertEqual(notification.get_attachment(todo), [])

	def test_send_only_once(self):
		config = {
			"name": "_Test Send Only Once",
			"subject": "_Test Send Only Once",
			"document_type": "ToDo",
			"event": "Save",
			"channel": "Email",
			"message": "Test send only once",
			"send_only_once": 1,
			"recipients": [{"receiver_by_document_field": "owner"}],
		}
		with get_test_notification(config):
			todo = frappe.get_doc(doctype="ToDo", description="Test send only once").insert()
			self.assertEqual(len(self.get_email_queue_for("ToDo", todo.name)), 1)

			todo.description = "Test send only once, changed"
			todo.save()
			self.assertEqual(len(self.get_email_queue_for("ToDo", todo.name)), 1)

			other_todo = frappe.get_doc(doctype="ToDo", description="Test send only once, other").insert()
			self.assertEqual(len(self.get_email_queue_for("ToDo", other_todo.name)), 1)

	def test_email_template(self):
		email_template = frappe.get_doc(
			doctype="Email Template",
			name="_Test Notification Email Template",
			subject="Template subject {{ doc.description }}",
			response="Template message {{ doc.name }}",
		).insert(ignore_if_duplicate=True)
		self.addCleanup(email_template.delete, ignore_permissions=True)

		config = {
			"name": "_Test Notification With Email Template",
			"subject": "Own subject",
			"document_type": "ToDo",
			"event": "New",
			"channel": "Email",
			"message": "Own message",
			"use_email_template": 1,
			"email_template": email_template.name,
			"recipients": [{"receiver_by_document_field": "owner"}],
		}
		with get_test_notification(config) as notification:
			todo = frappe.get_doc(doctype="ToDo", description="Test template").insert()

			communication = self.get_communications_for("ToDo", todo.name)[0]
			self.assertEqual(communication.subject, "Template subject Test template")
			self.assertIn(f"Template message {todo.name}", communication.content)

			# the system notification reuses what the email rendered
			notification.send_system_notification = 1
			with patch(
				"frappe.email.doctype.notification.notification.enqueue_create_notification"
			) as enqueue_create_notification:
				notification.send(todo)

			notification_doc = enqueue_create_notification.call_args.args[1]
			self.assertEqual(notification_doc["subject"], "Template subject Test template")
			self.assertIn(f"Template message {todo.name}", notification_doc["email_content"])

	def test_timeline_field(self):
		config = {
			"name": "_Test Notification Timeline",
			"subject": "_Test Notification Timeline",
			"document_type": "ToDo",
			"event": "New",
			"channel": "Email",
			"message": "Test timeline",
			"timeline_field": "assigned_by",
			"recipients": [{"receiver_by_document_field": "owner"}],
		}
		with get_test_notification(config) as notification:
			todo = frappe.get_doc(
				doctype="ToDo",
				description="Test timeline",
				assigned_by="test@example.com",
				reference_type="User",
				reference_name="test1@example.com",
			).insert()

			communication = self.get_communications_for("ToDo", todo.name)[0]
			timeline_links = frappe.get_all(
				"Communication Link",
				filters={"parent": communication.name},
				fields=["link_doctype", "link_name"],
			)
			self.assertIn({"link_doctype": "User", "link_name": "test@example.com"}, timeline_links)

			notification.timeline_field = "reference_name"
			self.assertEqual(notification.get_timeline_doctype_and_name(todo), ("User", "test1@example.com"))

			notification.timeline_field = "description"
			self.assertEqual(notification.get_timeline_doctype_and_name(todo), (None, None))

	def test_recipient_template(self):
		config = {
			"name": "_Test Notification Recipient Template",
			"subject": "_Test Notification Recipient Template",
			"document_type": "ToDo",
			"event": "New",
			"channel": "Email",
			"message": "Test recipient template",
			"recipients": [{"recipient": "{{ doc.assigned_by }},test2@example.com"}],
		}
		with get_test_notification(config) as notification:
			todo = frappe.new_doc(
				"ToDo", description="Test recipient template", assigned_by="test1@example.com"
			)
			context = {"doc": todo}

			recipients, _cc, _bcc = notification.get_list_of_recipients(todo, context)
			self.assertCountEqual(recipients, ["test1@example.com", "test2@example.com"])

			notification.recipients[0].recipient = "{{ doc.description }}"
			todo.description = "+971 50-123 4567"
			self.assertEqual(notification.get_receiver_list(todo, context), ["+971501234567"])

	def test_context_reaches_condition_and_message(self):
		from frappe.email.doctype.notification.notification import evaluate_alert

		config = {
			"name": "_Test Notification Context",
			"subject": "_Test Notification Context",
			"document_type": "ToDo",
			"event": "Method",
			"method": "_test_never_called",
			"channel": "Email",
			# the context isn't there when the condition is validated on save
			"condition": "not doc.name or extra == 'Send'",
			"message": "Extra: {{ extra }}",
			"recipients": [{"receiver_by_document_field": "owner"}],
		}
		with get_test_notification(config) as notification:
			todo = frappe.get_doc(doctype="ToDo", description="Test context").insert()

			evaluate_alert(todo, notification.name, notification.event, context={"extra": "Skip"})
			self.assertFalse(self.get_communications_for("ToDo", todo.name))

			evaluate_alert(todo, notification.name, notification.event, context={"extra": "Send"})
			self.assertIn("Extra: Send", self.get_communications_for("ToDo", todo.name)[0].content)

	@patch("frappe.are_sms_muted", return_value=False)
	def test_sms_channel(self, are_sms_muted):
		from frappe.core.doctype.notification_count.notification_count import (
			get_notification_last_scheduled,
		)

		config = {
			"name": "_Test SMS Notification",
			"document_type": "ToDo",
			"event": "New",
			"channel": "SMS",
			"message": "SMS for {{ doc.description }}",
			"notification_key": "_Test SMS Key",
			"timeline_field": "assigned_by",
			"recipients": [{"recipient": "+971501234567"}],
		}
		with get_test_notification(config):
			todo = frappe.get_doc(
				doctype="ToDo", description="Test SMS notification", assigned_by="test@example.com"
			).insert()

			sms_queue = frappe.get_all(
				"SMS Queue",
				filters={"reference_doctype": "ToDo", "reference_name": todo.name},
				fields=["name", "message", "notification_key", "party_doctype", "party", "communication"],
			)
			self.assertEqual(len(sms_queue), 1)
			self.assertEqual(sms_queue[0].message, "SMS for Test SMS notification")
			self.assertEqual(sms_queue[0].notification_key, "_Test SMS Key")
			self.assertEqual((sms_queue[0].party_doctype, sms_queue[0].party), ("User", "test@example.com"))
			self.assertEqual(
				frappe.get_all("SMS Queue Recipient", {"parent": sms_queue[0].name}, pluck="recipient"),
				["+971501234567"],
			)

			communication = frappe.get_doc("Communication", sms_queue[0].communication)
			self.assertEqual(communication.communication_medium, "SMS")
			self.assertEqual(communication.communication_type, "Automated Message")
			self.assertEqual(communication.subject, "_Test SMS Key SMS")

			self.assertTrue(get_notification_last_scheduled("ToDo", todo.name, "_Test SMS Key", "SMS"))

			# muted SMS: nothing is queued
			are_sms_muted.return_value = True
			muted_todo = frappe.get_doc(doctype="ToDo", description="Test muted SMS").insert()
			self.assertFalse(
				frappe.get_all("SMS Queue", {"reference_doctype": "ToDo", "reference_name": muted_todo.name})
			)

	def test_has_notification_with_trigger_method(self):
		from frappe.email.doctype.notification.notification import has_notification

		self.assertTrue(has_notification("ToDo", "_Test No Such Key", trigger_method="validate"))
		self.assertFalse(has_notification("ToDo", "_Test No Such Key", trigger_method="_test_no_such_method"))

	@classmethod
	def tearDownClass(cls):
		frappe.delete_doc_if_exists("Notification", "ToDo Status Update")
		frappe.delete_doc_if_exists("Notification", "Contact Status Update")
