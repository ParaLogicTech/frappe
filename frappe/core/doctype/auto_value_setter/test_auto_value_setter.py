# Copyright (c) 2019, Frappe Technologies and Contributors
# See license.txt

import frappe
from frappe.core.doctype.doctype.test_doctype import new_doctype
from frappe.tests.utils import FrappeTestCase

TEST_DOCTYPE = "Test Auto Value Doc"
TEST_ROW_DOCTYPE = "Test Auto Value Row"


def make_test_doctypes():
	if not frappe.db.exists("DocType", TEST_ROW_DOCTYPE):
		new_doctype(
			TEST_ROW_DOCTYPE,
			istable=1,
			allow_auto_value_setter=1,
			fields=[{"fieldname": "parent_title", "fieldtype": "Data", "label": "Parent Title"}],
		).insert()

	if not frappe.db.exists("DocType", TEST_DOCTYPE):
		new_doctype(
			TEST_DOCTYPE,
			is_submittable=1,
			allow_auto_value_setter=1,
			fields=[
				{"fieldname": "title", "fieldtype": "Data", "label": "Title"},
				{"fieldname": "code", "fieldtype": "Data", "label": "Code"},
				{"fieldname": "remarks", "fieldtype": "Data", "label": "Remarks", "allow_on_submit": 1},
				{"fieldname": "items", "fieldtype": "Table", "label": "Items", "options": TEST_ROW_DOCTYPE},
			],
			permissions=[
				{"role": "System Manager", "read": 1, "write": 1, "create": 1, "submit": 1, "cancel": 1}
			],
		).insert()


class TestAutoValueSetter(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		make_test_doctypes()
		super().setUpClass()

	def tearDown(self):
		# the cache would outlive the rollback of this test's setters
		for doctype in (TEST_DOCTYPE, TEST_ROW_DOCTYPE):
			for name in frappe.get_all("Auto Value Setter", {"document_type": doctype}, pluck="name"):
				frappe.delete_doc("Auto Value Setter", name)
			frappe.cache.hdel("auto_value_setters", doctype)

	def make_setter(self, field_name, conditions, document_type=TEST_DOCTYPE, **values):
		return frappe.get_doc(
			doctype="Auto Value Setter",
			document_type=document_type,
			field_name=field_name,
			enabled=1,
			conditions=[{"condition": condition, "value": value} for condition, value in conditions],
			**values,
		).insert()

	def make_doc(self, **values):
		return frappe.get_doc({"doctype": TEST_DOCTYPE, "title": "Test", **values})

	def test_validation(self):
		for document_type, field_name, error in (
			("Auto Value Setter", "field_name", "for itself"),
			("DocType", "name", "for itself"),
			("Auto Value Setter Condition", "value", "for itself"),
			("ToDo", "description", "not allowed"),
			(TEST_DOCTYPE, "_no_such_field", "does not exist"),
		):
			self.assertRaisesRegex(
				frappe.ValidationError, error, self.make_setter, field_name, [], document_type=document_type
			)

		self.assertRaises(frappe.ValidationError, self.make_setter, "code", [("", "{{ doc.title ")])

	def test_conditions_in_order(self):
		self.make_setter("code", [("doc.title == 'Special'", "SPECIAL"), ("", "CODE-{{ doc.title }}")])

		self.assertEqual(self.make_doc(title="Special").insert().code, "SPECIAL")

		doc = self.make_doc(title="Plain", code="Typed").insert()
		self.assertEqual(doc.code, "CODE-Plain")

		# applied again on save
		doc.title = "Changed"
		doc.save()
		self.assertEqual(doc.code, "CODE-Changed")

	def test_set_if_empty_and_for_new_document(self):
		setter = self.make_setter("code", [("", "CODE-{{ doc.title }}")], set_if_empty=1)
		self.assertEqual(self.make_doc(code="Typed").insert().code, "Typed")
		self.assertEqual(self.make_doc(title="Empty").insert().code, "CODE-Empty")

		setter.set_if_empty = 0
		setter.set_for_new_document = 1
		setter.save()

		doc = self.make_doc(title="New").insert()
		self.assertEqual(doc.code, "CODE-New")
		doc.title = "Saved"
		doc.save()
		self.assertEqual(doc.code, "CODE-New")

	def test_disabled_and_ignored(self):
		setter = self.make_setter("code", [("", "CODE")])

		doc = self.make_doc(code="Typed")
		doc.flags.ignore_auto_value_setters = True
		self.assertEqual(doc.insert().code, "Typed")

		setter.enabled = 0
		setter.save()
		self.assertEqual(self.make_doc(code="Typed").insert().code, "Typed")

	def test_submitted_document(self):
		self.make_setter("code", [("", "CODE-{{ doc.remarks }}")])
		self.make_setter("remarks", [("doc.docstatus == 1", "Submitted")])

		doc = self.make_doc(remarks="Draft").insert()
		self.assertEqual(doc.code, "CODE-Draft")
		doc.submit()

		# only allow-on-submit fields are set after submission
		doc.save()
		self.assertEqual((doc.code, doc.remarks), ("CODE-Draft", "Submitted"))

	def test_rows_get_parent_context(self):
		self.make_setter("parent_title", [("", "{{ parent.title }}")], document_type=TEST_ROW_DOCTYPE)

		doc = self.make_doc(title="Parent", items=[{}, {}]).insert()
		self.assertEqual([d.parent_title for d in doc.items], ["Parent", "Parent"])
