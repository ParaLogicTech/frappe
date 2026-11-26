import datetime

import frappe
from frappe import format
from frappe.tests.utils import FrappeTestCase
from frappe.utils import fmt_money
from frappe.utils.formatters import format_value


class TestFormatter(FrappeTestCase):
	def test_currency_formatting(self):
		df = frappe._dict({"fieldname": "amount", "fieldtype": "Currency", "options": "currency"})

		doc = frappe._dict({"amount": 5})
		frappe.db.set_default("currency", "INR")

		# if currency field is not passed then default currency should be used.
		self.assertEqual(format(100000, df, doc, format="#,###.##"), "₹ 100,000.00")

		doc.currency = "USD"
		self.assertEqual(format(100000, df, doc, format="#,###.##"), "$ 100,000.00")

		frappe.db.set_default("currency", None)

	def test_percent(self):
		self.assertEqual(format(12.5, {"fieldtype": "Percent"}), "12.5%")
		self.assertEqual(format(12.0, {"fieldtype": "Percent"}), "12%")
		self.assertEqual(format(12.004, {"fieldtype": "Percent"}), "12%")
		self.assertEqual(format(12.346, {"fieldtype": "Percent"}), "12.35%")
		self.assertEqual(format_value(12.346, {"fieldtype": "Percent"}, precision=1), "12.3%")

	def test_numbers(self):
		self.assertEqual(format(1234567, {"fieldtype": "Int"}, format="#,###.##"), "1,234,567")
		self.assertEqual(format_value(1.0000001, {"fieldtype": "Float"}), "1")
		self.assertEqual(
			format_value(1234.5678, {"fieldtype": "Float"}, precision=1), fmt_money(1234.6, precision=1)
		)
		self.assertEqual(
			format_value(1234.5678, {"fieldtype": "Currency"}, currency="USD", precision=0),
			fmt_money(1235, precision=0, currency="USD"),
		)

	def test_currency_symbol(self):
		for key, value in (("hide_currency_symbol", "Yes"), ("currency", "USD")):
			previous = frappe.db.get_default(key)
			frappe.db.set_default(key, value)
			self.addCleanup(frappe.db.set_default, key, previous)

		df = {"fieldtype": "Currency"}
		self.assertEqual(format_value(10, df, currency="USD"), "10.00")
		self.assertEqual(format_value(10, {**df, "force_currency_symbol": 1}, currency="USD"), "$ 10.00")
		# another currency always shows its symbol
		self.assertEqual(format_value(10, df, currency="EUR"), "€ 10.00")

	def test_time_and_text(self):
		self.assertEqual(format(datetime.time(10, 30)), format("10:30:00", {"fieldtype": "Time"}))
		self.assertEqual(format(5, {"fieldtype": "Text"}), "5")
