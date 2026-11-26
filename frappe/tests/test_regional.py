# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.regional.regional import (
	_validate_duplicate_email,
	_validate_duplicate_mobile_no,
	get_all_mobile_formats,
	local_to_international_mobile_no,
	validate_mobile_no,
	validate_tax_ids,
)
from frappe.tests.utils import FrappeTestCase


class TestMobileFormats(FrappeTestCase):
	def set_default_country(self, country):
		previous_country = frappe.db.get_default("country")
		frappe.db.set_default("country", country)
		self.addCleanup(frappe.db.set_default, "country", previous_country)

	def test_all_formats_from_any_format(self):
		for country, formats in (
			("Pakistan", ["03001112233", "+923001112233", "00923001112233"]),
			("United Arab Emirates", ["0501112233", "+971501112233", "00971501112233"]),
		):
			self.set_default_country(country)
			for mobile_no in formats:
				self.assertCountEqual(get_all_mobile_formats(mobile_no), formats, f"{country}: {mobile_no}")

	def test_given_format_comes_first(self):
		self.set_default_country("Pakistan")
		self.assertEqual(get_all_mobile_formats(" +923001112233 ")[0], "+923001112233")

	def test_number_from_another_country(self):
		self.set_default_country("Pakistan")
		self.assertEqual(get_all_mobile_formats("+971501112233"), ["+971501112233"])

	def test_country_without_mobile_prefixes(self):
		self.set_default_country("United States")
		self.assertEqual(get_all_mobile_formats("4155550100"), ["4155550100"])

	def test_empty(self):
		self.assertEqual(get_all_mobile_formats(None), [])
		self.assertEqual(get_all_mobile_formats(" "), [])

	def test_local_to_international(self):
		self.set_default_country("Pakistan")
		for mobile_no in ("03001112233", "3001112233", "+923001112233", "00923001112233"):
			self.assertEqual(local_to_international_mobile_no(mobile_no), "+923001112233", mobile_no)

		self.set_default_country("United States")
		self.assertEqual(local_to_international_mobile_no("4155550100"), "4155550100")


class TestRegionalValidation(FrappeTestCase):
	def set_default_country(self, country):
		previous_country = frappe.db.get_default("country")
		frappe.db.set_default("country", country)
		self.addCleanup(frappe.db.set_default, "country", previous_country)

	def test_mobile_no_pakistan(self):
		self.set_default_country("Pakistan")

		self.assertTrue(validate_mobile_no("0300-1112233"))
		# international numbers aren't checked
		self.assertTrue(validate_mobile_no("+971501112233"))
		self.assertTrue(validate_mobile_no("00971501112233"))

		self.assertFalse(validate_mobile_no("03001112233", throw=False))
		self.assertFalse(validate_mobile_no("", throw=False))
		self.assertRaises(frappe.ValidationError, validate_mobile_no, "042-1112233")

	def test_mobile_no_uae(self):
		self.set_default_country("United Arab Emirates")

		for mobile_no in ("0501112233", "+971501112233", "00971501112233", "+923001112233"):
			self.assertTrue(validate_mobile_no(mobile_no), mobile_no)

		self.assertFalse(validate_mobile_no("0591112233", throw=False))
		self.assertRaises(frappe.ValidationError, validate_mobile_no, "+97142345678")

	def test_mobile_no_other_countries(self):
		self.set_default_country("United States")
		self.assertTrue(validate_mobile_no("anything"))
		self.assertFalse(validate_mobile_no(""))

	def test_tax_ids(self):
		self.set_default_country("Pakistan")
		validate_tax_ids(tax_id="1234567-8", tax_cnic="12345-1234567-1", tax_strn="12-34-5678-901-23")
		self.assertRaises(frappe.ValidationError, validate_tax_ids, tax_id="12345678")
		self.assertRaises(frappe.ValidationError, validate_tax_ids, tax_cnic="1234512345671")
		self.assertRaises(frappe.ValidationError, validate_tax_ids, tax_strn="1234567890123")

		self.set_default_country("United Arab Emirates")
		validate_tax_ids(tax_id="123456789012345", tax_cnic="784-1234-1234567-1")
		self.assertRaises(frappe.ValidationError, validate_tax_ids, tax_id="12345")
		self.assertRaises(frappe.ValidationError, validate_tax_ids, tax_cnic="784123412345671")

		self.set_default_country("United States")
		validate_tax_ids(tax_id="anything", tax_cnic="anything")

	def test_duplicate_mobile_no_in_any_format(self):
		self.set_default_country("United Arab Emirates")
		contact = frappe.get_doc(doctype="Contact", first_name="Duplicate", mobile_no="0501112233").insert()

		self.assertRaises(
			frappe.ValidationError,
			_validate_duplicate_mobile_no,
			"Contact",
			"mobile_no",
			"+971501112233",
			throw=True,
		)
		_validate_duplicate_mobile_no(
			"Contact", "mobile_no", "00971501112233", exclude=contact.name, throw=True
		)
		# invalid numbers aren't checked
		_validate_duplicate_mobile_no("Contact", "mobile_no", "0591112233", throw=True)

		# without throw it only warns
		frappe.clear_messages()
		_validate_duplicate_mobile_no("Contact", "mobile_no", "+971501112233")
		self.assertIn(contact.name, frappe.message_log[-1].get("message"))

	def test_duplicate_email(self):
		contact = frappe.get_doc(
			doctype="Contact", first_name="Duplicate", email_id="duplicate@example.com"
		).insert()

		self.assertRaises(
			frappe.ValidationError,
			_validate_duplicate_email,
			"Contact",
			"email_id",
			" duplicate@example.com ",
			throw=True,
		)
		_validate_duplicate_email(
			"Contact", "email_id", "duplicate@example.com", exclude=contact.name, throw=True
		)
		_validate_duplicate_email("Contact", "email_id", "not an email", throw=True)
		self.assertRaises(
			frappe.ValidationError, _validate_duplicate_email, "Contact", "no_such_field", "x@example.com"
		)
