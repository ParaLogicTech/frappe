# Copyright (c) 2017, Frappe Technologies and Contributors
# License: MIT. See LICENSE
from unittest.mock import patch

import frappe
from frappe.core.doctype.notification_count.notification_count import get_notification_count
from frappe.core.doctype.sms_settings.sms_settings import process_and_send
from frappe.tests.utils import FrappeTestCase


class TestSMSSettings(FrappeTestCase):
	def setUp(self):
		frappe.db.set_single_value("SMS Settings", "sms_gateway_url", "https://sms.example.com/send")

	def get_sms_args(self, **kwargs):
		return {
			"receiver_list": ["+971501234567"],
			"message": "Test notification key",
			"reference_doctype": "User",
			"reference_name": "Administrator",
			"notification_key": "_Test Key",
			**kwargs,
		}

	@patch("frappe.core.doctype.sms_settings.sms_settings.send_via_gateway")
	def test_sent_sms_adds_notification_count(self, send_via_gateway):
		process_and_send(self.get_sms_args())

		send_via_gateway.assert_called_once()
		self.assertEqual(get_notification_count("User", "Administrator", "_Test Key", "SMS"), 1)

	@patch("frappe.email.doctype.notification.notification.run_validate_notification", return_value=0)
	@patch("frappe.core.doctype.sms_settings.sms_settings.send_via_gateway")
	def test_failed_validation_stops_sms(self, send_via_gateway, run_validate_notification):
		doc = frappe.get_doc("User", "Administrator")

		self.assertRaises(frappe.ValidationError, process_and_send, self.get_sms_args(doc=doc))

		run_validate_notification.assert_called_once_with(
			doc, "_Test Key", child_doctype=None, child_name=None, throw=True
		)
		send_via_gateway.assert_not_called()
		self.assertEqual(get_notification_count("User", "Administrator", "_Test Key", "SMS"), 0)
