# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.regional.regional import get_all_mobile_formats
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
