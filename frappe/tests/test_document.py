# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
from contextlib import contextmanager
from datetime import timedelta
from unittest.mock import Mock, patch

import frappe
from frappe.app import make_form_dict
from frappe.core.doctype.doctype.test_doctype import new_doctype
from frappe.desk.doctype.note.note import Note
from frappe.model.base_document import BaseDocument
from frappe.model.document import Document
from frappe.model.naming import make_autoname, parse_naming_series, revert_series_if_last
from frappe.tests.utils import FrappeTestCase, timeout
from frappe.utils import cint, fmt_money, get_datetime, now_datetime, set_request
from frappe.website.serve import get_response


class CustomTestNote(Note):
	@property
	def age(self):
		return now_datetime() - self.creation


class CustomNoteWithoutProperty(Note):
	def age(self):
		return now_datetime() - self.creation


class TestDocument(FrappeTestCase):
	def test_get_return_empty_list_for_table_field_if_none(self):
		d = frappe.get_doc({"doctype": "User"})
		self.assertEqual(d.get("roles"), [])

	def test_load(self):
		d = frappe.get_doc("DocType", "User")
		self.assertEqual(d.doctype, "DocType")
		self.assertEqual(d.name, "User")
		self.assertEqual(d.allow_rename, 1)
		self.assertTrue(isinstance(d.fields, list))
		self.assertTrue(isinstance(d.permissions, list))
		self.assertTrue(filter(lambda d: d.fieldname == "email", d.fields))

	def test_load_single(self):
		d = frappe.get_doc("Website Settings", "Website Settings")
		self.assertEqual(d.name, "Website Settings")
		self.assertEqual(d.doctype, "Website Settings")
		self.assertTrue(d.disable_signup in (0, 1))

	def test_insert(self):
		d = frappe.get_doc(
			{
				"doctype": "Event",
				"subject": "test-doc-test-event 1",
				"starts_on": "2014-01-01",
				"event_type": "Public",
			}
		)
		d.insert()
		self.assertTrue(d.name.startswith("EV"))
		self.assertEqual(frappe.db.get_value("Event", d.name, "subject"), "test-doc-test-event 1")

		# test if default values are added
		self.assertEqual(d.send_reminder, 1)
		return d

	def test_website_route_default(self):
		default = frappe.generate_hash()
		child_table = new_doctype(default=default, istable=1).insert().name
		parent = (
			new_doctype(fields=[{"fieldtype": "Table", "options": child_table, "fieldname": "child_table"}])
			.insert()
			.name
		)

		doc = frappe.get_doc({"doctype": parent, "child_table": [{"some_fieldname": "xasd"}]}).insert()
		doc.append("child_table", {})
		doc.save()
		self.assertEqual(doc.child_table[-1].some_fieldname, default)

	def test_insert_with_child(self):
		d = frappe.get_doc(
			{
				"doctype": "Event",
				"subject": "test-doc-test-event 2",
				"starts_on": "2014-01-01",
				"event_type": "Public",
			}
		)
		d.insert()
		self.assertTrue(d.name.startswith("EV"))
		self.assertEqual(frappe.db.get_value("Event", d.name, "subject"), "test-doc-test-event 2")

	def test_update(self):
		d = self.test_insert()
		d.subject = "subject changed"
		d.save()

		self.assertEqual(frappe.db.get_value(d.doctype, d.name, "subject"), "subject changed")

	def test_value_changed(self):
		d = self.test_insert()
		d.subject = "subject changed again"
		d.load_doc_before_save()
		d.update_modified()

		self.assertTrue(d.has_value_changed("subject"))
		self.assertTrue(d.has_value_changed("modified"))

		self.assertFalse(d.has_value_changed("creation"))
		self.assertFalse(d.has_value_changed("event_type"))

	def test_mandatory(self):
		# TODO: recheck if it is OK to force delete
		frappe.delete_doc_if_exists("User", "test_mandatory@example.com", 1)

		d = frappe.get_doc(
			{
				"doctype": "User",
				"email": "test_mandatory@example.com",
			}
		)
		self.assertRaises(frappe.MandatoryError, d.insert)

		d.set("first_name", "Test Mandatory")
		d.insert()
		self.assertEqual(frappe.db.get_value("User", d.name), d.name)

	def test_text_editor_field(self):
		try:
			frappe.get_doc(doctype="Activity Log", subject="test", message='<img src="test.png" />').insert()
		except frappe.MandatoryError:
			self.fail("Text Editor false positive mandatory error")

	def test_conflict_validation(self):
		d1 = self.test_insert()
		d2 = frappe.get_doc(d1.doctype, d1.name)
		d1.save()
		self.assertRaises(frappe.TimestampMismatchError, d2.save)

	def test_save_after_insert_on_a_whole_second(self):
		with self.freeze_time("2026-10-15 10:33:29"):
			event = self.test_insert()

		event.subject = "saved after a whole-second insert"
		event.save()

		saved = frappe.db.get_value("Event", event.name, ["subject", "creation"], as_dict=True)
		self.assertEqual(saved.subject, "saved after a whole-second insert")
		self.assertEqual(saved.creation, get_datetime("2026-10-15 10:33:29"))

	def test_first_save_of_a_single(self):
		doctype = new_doctype(
			issingle=1, fields=[{"fieldname": "note", "fieldtype": "Data", "label": "Note"}]
		).insert()

		single = frappe.get_doc(doctype.name)
		single.note = "first save"
		single.save()

		self.assertEqual(frappe.db.get_single_value(doctype.name, "note"), "first save")

	def test_conflict_validation_single(self):
		d1 = frappe.get_doc("Website Settings", "Website Settings")
		d1.home_page = "test-web-page-1"

		d2 = frappe.get_doc("Website Settings", "Website Settings")
		d2.home_page = "test-web-page-1"

		d1.save()
		self.assertRaises(frappe.TimestampMismatchError, d2.save)

	def test_permission(self):
		frappe.set_user("Guest")
		self.assertRaises(frappe.PermissionError, self.test_insert)
		frappe.set_user("Administrator")

	def test_permission_single(self):
		frappe.set_user("Guest")
		d = frappe.get_doc("Website Settings", "Website Settings")
		self.assertRaises(frappe.PermissionError, d.save)
		frappe.set_user("Administrator")

	def test_link_validation(self):
		frappe.delete_doc_if_exists("User", "test_link_validation@example.com", 1)

		d = frappe.get_doc(
			{
				"doctype": "User",
				"email": "test_link_validation@example.com",
				"first_name": "Link Validation",
				"roles": [{"role": "ABC"}],
			}
		)
		self.assertRaises(frappe.LinkValidationError, d.insert)

		d.roles = []
		d.append("roles", {"role": "System Manager"})
		d.insert()

		self.assertEqual(frappe.db.get_value("User", d.name), d.name)

	def test_validate(self):
		d = self.test_insert()
		d.starts_on = "2014-01-01"
		d.ends_on = "2013-01-01"
		self.assertRaises(frappe.ValidationError, d.validate)
		self.assertRaises(frappe.ValidationError, d.run_method, "validate")
		self.assertRaises(frappe.ValidationError, d.save)

	def test_db_set_no_query_on_new_docs(self):
		user = frappe.new_doc("User")
		user.db_set("user_type", "Magical Wizard")
		with self.assertQueryCount(0):
			user.db_set("user_type", "Magical Wizard")

	def test_new_doc_with_fields(self):
		user = frappe.new_doc("User", first_name="wizard")
		self.assertEqual(user.first_name, "wizard")

	def test_update_after_submit(self):
		d = self.test_insert()
		d.starts_on = "2014-09-09"
		self.assertRaises(frappe.UpdateAfterSubmitError, d.validate_update_after_submit)
		d.meta.get_field("starts_on").allow_on_submit = 1
		d.validate_update_after_submit()
		d.meta.get_field("starts_on").allow_on_submit = 0

		# when comparing date(2014, 1, 1) and "2014-01-01"
		d.reload()
		d.starts_on = "2014-01-01"
		d.validate_update_after_submit()

	def test_varchar_length(self):
		d = self.test_insert()
		d.sender = "abcde" * 100 + "@user.com"
		self.assertRaises(frappe.CharacterLengthExceededError, d.save)

	def test_varchar_length_after_sanitization(self):
		unclosed_tag = "<strong>"
		value = "X" * (140 - len(unclosed_tag)) + unclosed_tag

		with self.set_user("test@example.com"):
			doc = frappe.new_doc("Note")
			doc.title = value

			with self.assertRaises(frappe.CharacterLengthExceededError):
				doc._validate()

		self.assertGreater(len(doc.title), 140)

	def test_oversized_varchar_sanitized_within_limit(self):
		value = "X" * 130 + '<p onclick="alert(1)">x</p>'
		self.assertGreater(len(value), 140)

		with self.set_user("test@example.com"):
			doc = frappe.new_doc("Note")
			doc.title = value
			doc._validate()

		self.assertEqual(doc.title, "X" * 130 + "<p>x</p>")

	def test_child_varchar_length_after_sanitization(self):
		unclosed_tag = "<strong>"
		value = "X" * (140 - len(unclosed_tag)) + unclosed_tag

		with self.set_user("test@example.com"):
			doc = frappe.new_doc("Workspace")
			doc.update(
				{"label": "Test Workspace", "module": "Core", "title": "Test Workspace", "type": "Workspace"}
			)
			doc.name = "Test Workspace"
			doc.append("shortcuts", {"type": "URL", "label": value})

			with self.assertRaises(frappe.CharacterLengthExceededError):
				doc._validate()

		self.assertGreater(len(doc.shortcuts[0].label), 140)

	def test_xss_filter(self):
		d = self.test_insert()

		# script
		xss = '<script>alert("XSS")</script>'
		escaped_xss = xss.replace("<", "&lt;").replace(">", "&gt;")
		d.subject += xss
		d.save()
		d.reload()

		self.assertTrue(xss not in d.subject)
		self.assertTrue(escaped_xss in d.subject)

		# onload
		xss = '<div onload="alert("XSS")">Test</div>'
		escaped_xss = "<div>Test</div>"
		d.subject += xss
		d.save()
		d.reload()

		self.assertTrue(xss not in d.subject)
		self.assertTrue(escaped_xss in d.subject)

		# css attributes
		xss = '<div style="something: doesn\'t work; color: red;">Test</div>'
		escaped_xss = '<div style="">Test</div>'
		d.subject += xss
		d.save()
		d.reload()

		self.assertTrue(xss not in d.subject)
		self.assertTrue(escaped_xss in d.subject)

	def test_naming_series(self):
		data = ["TEST-", "TEST/17-18/.test_data./.####", "TEST.YYYY.MM.####"]

		for series in data:
			name = make_autoname(series)
			prefix = series

			if ".#" in series:
				prefix = series.rsplit(".", 1)[0]

			prefix = parse_naming_series(prefix)
			old_current = frappe.db.get_value("Series", prefix, "current", order_by="name")

			revert_series_if_last(series, name)
			new_current = cint(frappe.db.get_value("Series", prefix, "current", order_by="name"))

			self.assertEqual(cint(old_current) - 1, new_current)

	def test_non_negative_check(self):
		frappe.delete_doc_if_exists("Currency", "Frappe Coin", 1)

		d = frappe.get_doc(
			{"doctype": "Currency", "currency_name": "Frappe Coin", "smallest_currency_fraction_value": -1}
		)

		self.assertRaises(frappe.NonNegativeError, d.insert)

		d.set("smallest_currency_fraction_value", 1)
		d.insert()
		self.assertEqual(frappe.db.get_value("Currency", d.name), d.name)

		frappe.delete_doc_if_exists("Currency", "Frappe Coin", 1)

	def test_get_formatted(self):
		frappe.get_doc(
			{
				"doctype": "DocType",
				"name": "Test Formatted",
				"module": "Custom",
				"custom": 1,
				"fields": [
					{"label": "Currency", "fieldname": "currency", "reqd": 1, "fieldtype": "Currency"},
				],
			}
		).insert(ignore_if_duplicate=True)

		frappe.delete_doc_if_exists("Currency", "INR", 1)

		d = frappe.get_doc(
			{
				"doctype": "Currency",
				"currency_name": "INR",
				"symbol": "₹",
			}
		).insert()

		d = frappe.get_doc({"doctype": "Test Formatted", "currency": 100000})
		self.assertEqual(d.get_formatted("currency", currency="INR", format="#,###.##"), "₹ 100,000.00")

		# should work even if options aren't set in df
		# and currency param is not passed
		self.assertIn("0", d.get_formatted("currency"))

	def test_limit_for_get(self):
		doc = frappe.get_doc("DocType", "DocType")
		# assuming DocType has more than 3 Data fields
		self.assertEqual(len(doc.get("fields", limit=3)), 3)

		# limit with filters
		self.assertEqual(len(doc.get("fields", filters={"fieldtype": "Data"}, limit=3)), 3)

	def test_virtual_fields(self):
		"""Virtual fields are accessible via API and Form views, whenever .as_dict is invoked"""
		frappe.db.delete("Custom Field", {"dt": "Note", "fieldname": "age"})
		note = frappe.new_doc("Note")
		note.content = "some content"
		note.title = frappe.generate_hash(length=20)
		note.insert()

		def patch_note(class_=None):
			return patch("frappe.controllers", new={frappe.local.site: {"Note": class_ or CustomTestNote}})

		@contextmanager
		def customize_note(with_options=False):
			options = (
				"frappe.utils.now_datetime() - frappe.utils.get_datetime(doc.creation)"
				if with_options
				else ""
			)
			custom_field = frappe.get_doc(
				{
					"doctype": "Custom Field",
					"dt": "Note",
					"fieldname": "age",
					"fieldtype": "Data",
					"read_only": True,
					"is_virtual": True,
					"options": options,
				}
			)

			try:
				yield custom_field.insert(ignore_if_duplicate=True)
			finally:
				custom_field.delete()
				# to truly delete the field
				# creation is commited due to DDL
				frappe.db.commit()

		with patch_note():
			doc = frappe.get_last_doc("Note")
			self.assertIsInstance(doc, CustomTestNote)
			self.assertIsInstance(doc.age, timedelta)
			self.assertIsNone(doc.as_dict().get("age"))
			self.assertIsNone(doc.get_valid_dict().get("age"))

		with customize_note(), patch_note():
			doc = frappe.get_last_doc("Note")
			self.assertIsInstance(doc, CustomTestNote)
			self.assertIsInstance(doc.age, timedelta)
			self.assertIsInstance(doc.as_dict().get("age"), timedelta)
			self.assertIsInstance(doc.get_valid_dict().get("age"), timedelta)

		# has virtual field, but age method is not a property
		with customize_note(), patch_note(class_=CustomNoteWithoutProperty):
			doc = frappe.get_last_doc("Note")
			self.assertIsInstance(doc, CustomNoteWithoutProperty)
			self.assertNotIsInstance(type(doc).age, property)
			self.assertIsNone(doc.as_dict().get("age"))
			self.assertIsNone(doc.get_valid_dict().get("age"))

		with customize_note(with_options=True):
			doc = frappe.get_last_doc("Note")
			self.assertIsInstance(doc, Note)
			self.assertIsInstance(doc.as_dict().get("age"), timedelta)
			self.assertIsInstance(doc.get_valid_dict().get("age"), timedelta)

	def test_run_method(self):
		doc = frappe.get_last_doc("User")

		# Case 1: Override with a string
		doc.as_dict = ""

		# run_method should throw TypeError
		self.assertRaisesRegex(TypeError, "not callable", doc.run_method, "as_dict")

		# Case 2: Override with a function
		def my_as_dict(*args, **kwargs):
			return "success"

		doc.as_dict = my_as_dict

		# run_method should get overridden
		self.assertEqual(doc.run_method("as_dict"), "success")

	def test_extend(self):
		doc = frappe.get_last_doc("User")
		self.assertRaises(ValueError, doc.extend, "user_emails", None)

		# allow calling doc.extend with iterable objects
		doc.extend("user_emails", ())
		doc.extend("user_emails", [])
		doc.extend("user_emails", (x for x in ()))

	def test_set(self):
		doc = frappe.get_last_doc("User")

		# setting None should init a table field to empty list
		doc.set("user_emails", None)
		self.assertEqual(doc.user_emails, [])

		# setting a string value should fail
		self.assertRaises(TypeError, doc.set, "user_emails", "fail")
		# but not when loading from db
		doc.flags.ignore_children = True
		doc.update({"user_emails": "ok"})

	def test_doc_events(self):
		"""validate that all present doc events are correct methods"""

		for doctype, doc_hooks in frappe.get_doc_hooks().items():
			for _, hooks in doc_hooks.items():
				for hook in hooks:
					try:
						frappe.get_attr(hook)
					except Exception as e:
						self.fail(f"Invalid doc hook: {doctype}:{hook}\n{e}")

	def test_realtime_notify(self):
		todo = frappe.new_doc("ToDo")
		todo.description = "this will trigger realtime update"
		todo.notify_update = Mock()
		todo.insert()
		self.assertEqual(todo.notify_update.call_count, 1)

		todo.reload()
		todo.flags.notify_update = False
		todo.description = "this won't trigger realtime update"
		todo.save()
		self.assertEqual(todo.notify_update.call_count, 1)

	def test_error_on_saving_new_doc_with_name(self):
		"""Trying to save a new doc with name should raise DoesNotExistError"""

		doc = frappe.get_doc(
			{
				"doctype": "ToDo",
				"description": "this should raise frappe.DoesNotExistError",
				"name": "lets-trick-doc-save",
			}
		)

		self.assertRaises(frappe.DoesNotExistError, doc.save)

	def test_validate_from_to_dates(self):
		doc = frappe.new_doc("Web Page")
		doc.start_date = None
		doc.end_date = None
		doc.validate_from_to_dates("start_date", "end_date")

		doc.start_date = "2020-01-01"
		doc.end_date = None
		doc.validate_from_to_dates("start_date", "end_date")

		doc.start_date = None
		doc.end_date = "2020-12-31"
		doc.validate_from_to_dates("start_date", "end_date")

		doc.start_date = "2020-01-01"
		doc.end_date = "2020-12-31"
		doc.validate_from_to_dates("start_date", "end_date")

		doc.end_date = "2020-01-01"
		doc.start_date = "2020-12-31"
		self.assertRaises(
			frappe.exceptions.InvalidDates, doc.validate_from_to_dates, "start_date", "end_date"
		)

	def test_db_set_singles(self):
		c = frappe.get_doc("Contact Us Settings")
		key, val = "email_id", "admin1@example.com"
		c.db_set(key, val)
		changed_val = frappe.db.get_single_value(c.doctype, key)
		self.assertEqual(val, changed_val)

	def test_base_document_alias(self):
		self.assertIs(BaseDocument, Document)

	def test_docstatus(self):
		doc = Document({"docstatus": 0, "doctype": "ToDo"})
		self.assertTrue(doc.docstatus.is_draft())
		self.assertEqual(doc.docstatus, 0)

		doc.docstatus = 1
		self.assertTrue(doc.docstatus.is_submitted())
		self.assertEqual(doc.docstatus, 1)

		doc.docstatus = 2
		self.assertTrue(doc.docstatus.is_cancelled())
		self.assertEqual(doc.docstatus, 2)

	def test_super_document_init_sets_values(self):
		class LegacyVirtualToDo(Document):
			def load_from_db(self):
				super(Document, self).__init__(
					{"doctype": "ToDo", "name": self.name, "description": "legacy"}
				)

		with self.assertWarns(DeprecationWarning):
			doc = LegacyVirtualToDo("ToDo", "legacy-todo")

		self.assertEqual(doc.name, "legacy-todo")
		self.assertEqual(doc.description, "legacy")


class TestDocumentWebView(FrappeTestCase):
	def get(self, path, user="Guest"):
		frappe.set_user(user)
		set_request(method="GET", path=path)
		make_form_dict(frappe.local.request)
		response = get_response()
		frappe.set_user("Administrator")
		return response

	def test_web_view_link_authentication(self):
		todo = frappe.get_doc({"doctype": "ToDo", "description": "Test"}).insert()
		document_key = todo.get_document_share_key()

		# with old-style signature key
		old_document_key = todo.get_signature()
		url = f"/ToDo/{todo.name}?key={old_document_key}"
		self.assertEqual(self.get(url).status, "403 FORBIDDEN")

		# with valid key
		url = f"/ToDo/{todo.name}?key={document_key}"
		self.assertEqual(self.get(url).status, "200 OK")

		# with invalid key
		invalid_key_url = f"/ToDo/{todo.name}?key=INVALID_KEY"
		self.assertEqual(self.get(invalid_key_url).status, "403 FORBIDDEN")

		# expire the key
		document_key_doc = frappe.get_doc("Document Share Key", {"key": document_key})
		document_key_doc.expires_on = "2020-01-01"
		document_key_doc.save(ignore_permissions=True)

		# with expired key
		self.assertEqual(self.get(url).status, "410 GONE")

		# without key
		url_without_key = f"/ToDo/{todo.name}"
		self.assertEqual(self.get(url_without_key).status, "403 FORBIDDEN")

		# Logged-in user can access the page without key
		self.assertEqual(self.get(url_without_key, "Administrator").status, "200 OK")

	def test_bulk_inserts(self):
		from frappe.model.document import bulk_insert

		doctype = "Role Profile"
		child_field = "roles"
		child_doctype = frappe.get_meta(doctype).get_field(child_field).options

		sent_docs = set()
		sent_child_docs = set()

		def doc_generator():
			for _ in range(21):
				doc = frappe.new_doc(doctype)
				doc.role_profile = frappe.generate_hash()
				doc.append("roles", {"role": "System Manager"})

				doc.set_new_name()
				doc.set_parent_in_children()

				sent_docs.add(doc.name)
				sent_child_docs.add(doc.roles[0].name)

				yield doc

		bulk_insert(doctype, doc_generator(), chunk_size=5)

		all_docs = set(frappe.get_all(doctype, pluck="name"))
		all_child_docs = set(
			frappe.get_all(
				child_doctype, filters={"parenttype": doctype, "parentfield": child_field}, pluck="name"
			)
		)
		self.assertEqual(sent_docs - all_docs, set(), "All docs should be inserted")
		self.assertEqual(sent_child_docs - all_child_docs, set(), "All child docs should be inserted")

	def test_sanitize_content_skips_json_fieldtype(self):
		"""JSON field values must survive _sanitize_content untouched, even with
		HTML-like substrings, while ordinary text fields are still sanitized."""
		doctype = new_doctype(
			fields=[
				{"label": "Config", "fieldname": "config", "fieldtype": "JSON"},
				{"label": "Description", "fieldname": "description", "fieldtype": "Text"},
			]
		).insert()

		payload = '{"label": "<b onclick=\\"alert(1)\\">hi</b>"}'
		doc = frappe.get_doc(
			doctype=doctype.name, config=payload, description='<b onclick="alert(1)">hi</b>'
		).insert()

		self.assertEqual(doc.config, payload)
		self.assertNotIn("onclick", doc.description)


SUBMITTABLE_DOCTYPE = "Test Submittable With Rows"
SUBMITTABLE_ROW_DOCTYPE = "Test Submittable Row"


def make_submittable_doctypes():
	if not frappe.db.exists("DocType", SUBMITTABLE_ROW_DOCTYPE):
		new_doctype(
			SUBMITTABLE_ROW_DOCTYPE,
			istable=1,
			fields=[
				{"fieldname": "item", "fieldtype": "Data", "label": "Item"},
				{"fieldname": "qty", "fieldtype": "Float", "label": "Qty", "allow_on_submit": 1},
			],
		).insert()

	if not frappe.db.exists("DocType", SUBMITTABLE_DOCTYPE):
		new_doctype(
			SUBMITTABLE_DOCTYPE,
			is_submittable=1,
			fields=[
				{"fieldname": "title", "fieldtype": "Data", "label": "Title"},
				{"fieldname": "remarks", "fieldtype": "Data", "label": "Remarks", "allow_on_submit": 1},
				{"fieldname": "amount", "fieldtype": "Currency", "label": "Amount", "allow_on_submit": 1},
				{"fieldname": "price", "fieldtype": "Currency", "label": "Price"},
				{"fieldname": "rate", "fieldtype": "Float", "label": "Rate", "precision": "2"},
				{"fieldname": "discount", "fieldtype": "Percent", "label": "Discount", "non_negative": 1},
				{"fieldname": "user", "fieldtype": "Link", "label": "User", "options": "User"},
				{
					"fieldname": "user_name",
					"fieldtype": "Data",
					"label": "User Name",
					"fetch_from": "user.full_name",
				},
				{
					"fieldname": "items",
					"fieldtype": "Table",
					"label": "Items",
					"options": SUBMITTABLE_ROW_DOCTYPE,
					"allow_on_submit": 1,
				},
			],
			permissions=[
				{"role": "System Manager", "read": 1, "write": 1, "create": 1, "submit": 1, "cancel": 1}
			],
		).insert()


class TestDocumentValues(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		make_submittable_doctypes()
		super().setUpClass()

	def make_doc(self, **values):
		return frappe.get_doc(
			{
				"doctype": SUBMITTABLE_DOCTYPE,
				"title": "Test",
				"price": 100,
				"rate": 10,
				"items": [{"item": "Row 1", "qty": 1}],
				**values,
			}
		)

	def test_getone(self):
		doc = self.make_doc(items=[{"item": "Row 1"}, {"item": "Row 2"}])
		self.assertEqual(doc.getone("items").item, "Row 1")
		self.assertEqual(doc.getone("items", {"item": "Row 2"}).item, "Row 2")
		self.assertIsNone(doc.getone("items", {"item": "Row 3"}))

	def test_update_if_missing_with_force_fields(self):
		doc = self.make_doc(remarks=None)
		doc.update_if_missing({"title": "Other", "remarks": "Filled"})
		self.assertEqual((doc.title, doc.remarks), ("Test", "Filled"))

		doc.update_if_missing({"title": "Other", "price": None}, force_fields=["title", "price"])
		self.assertEqual((doc.title, doc.price), ("Other", None))

	def test_disallow_on_submit(self):
		doc = self.make_doc().insert()
		doc.submit()

		doc.flags.disallow_on_submit = doc.get_fields_for_disallow_on_submit(excluding_fields=["remarks"])
		self.assertCountEqual(
			doc.flags.disallow_on_submit, [("amount", None), ("items", None), ("qty", "items")]
		)

		doc.remarks = "Allowed"
		doc.save()

		doc.amount = 50
		self.assertRaises(frappe.UpdateAfterSubmitError, doc.save)
		doc.reload()

		doc.items[0].qty = 2
		self.assertRaises(frappe.UpdateAfterSubmitError, doc.save)
		doc.reload()

		# a new row in an allow-on-submit table is disallowed too
		doc.append("items", {"item": "Row 2"})
		self.assertRaises(frappe.UpdateAfterSubmitError, doc.save)
		doc.reload()

		# without the flag, the same changes are allowed
		doc.flags.disallow_on_submit = None
		doc.amount = 50
		doc.items[0].qty = 2
		doc.append("items", {"item": "Row 2"})
		doc.save()

	def test_float_noise_after_submit(self):
		doc = self.make_doc().insert()
		doc.submit()

		doc.price = 100.0000000000001
		doc.rate = 10.0000000000001
		doc.save()

		doc.price = 150
		with self.assertRaises(frappe.UpdateAfterSubmitError) as error:
			doc.save()
		self.assertIn(frappe.format(150, df=doc.meta.get_field("price"), doc=doc), str(error.exception))

	def test_get_formatted_precision_and_negative(self):
		doc = self.make_doc(rate=1234.567)
		self.assertEqual(doc.get_formatted("rate", precision=1), fmt_money(1234.6, precision=1))
		self.assertEqual(doc.get_formatted("rate", negative_value=True), fmt_money(-1234.57, precision=2))

	def test_non_negative_percent(self):
		self.assertRaises(frappe.NonNegativeError, self.make_doc(discount=-1).insert)

	def test_round_floats_in_excluding(self):
		doc = self.make_doc(rate=1.23456)
		doc.round_floats_in(doc, ["rate"], excluding=["rate"])
		self.assertEqual(doc.rate, 1.23456)

		doc.round_floats_in(doc, ["rate"])
		self.assertEqual(doc.rate, 1.23)

	def test_missing_link_with_fetch_from(self):
		doc = self.make_doc(user="_test_no_such_user@example.com")
		self.assertRaises(frappe.LinkValidationError, doc.insert)

		doc.user = "test@example.com"
		doc.insert()
		self.assertEqual(doc.user_name, frappe.db.get_value("User", "test@example.com", "full_name"))

	def test_before_validate_links(self):
		doc = self.make_doc()
		with patch.object(doc, "run_method", wraps=doc.run_method) as run_method:
			doc.insert()
			doc.submit()

		methods = [call.args[0] for call in run_method.call_args_list]
		# runs on save, not on submit
		self.assertEqual(methods.count("before_validate_links"), 1)

	def test_check_if_latest_without_docstatus_transition(self):
		doc = self.make_doc().insert()
		doc.submit()

		stale = frappe.get_doc(SUBMITTABLE_DOCTYPE, doc.name)
		stale.docstatus = 0
		# as save() sets it
		stale._original_modified = stale.modified
		self.assertRaises(frappe.ValidationError, stale.check_if_latest)
		stale.check_if_latest(check_docstatus_transition=False)

	def test_has_method(self):
		self.assertTrue(Document.has_method("ToDo", "validate"))
		self.assertFalse(Document.has_method("ToDo", "_test_no_such_method"))
		self.assertFalse(Document.has_method("_Test No Such DocType", "validate"))

		with patch.dict(frappe.get_doc_hooks(), {"ToDo": {"_test_hooked_method": ["frappe.msgprint"]}}):
			self.assertTrue(Document.has_method("ToDo", "_test_hooked_method"))
