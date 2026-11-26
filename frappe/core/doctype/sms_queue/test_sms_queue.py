# Copyright (c) 2022, Frappe Technologies and Contributors
# See license.txt

import frappe
from frappe.core.doctype.sms_settings.sms_settings import send_sms
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, now_datetime


class TestSMSQueue(FrappeTestCase):
	def test_queue_keeps_notification_key(self):
		send_sms(
			receiver_list=["+971501234567"],
			message="Test notification key",
			notification_key="_Test Key",
			reference_doctype="User",
			reference_name="Administrator",
			queue=True,
			# keeps the queued SMS from being sent by a background job
			send_after=add_days(now_datetime(), 1),
		)

		sms_queue = frappe.get_all(
			"SMS Queue",
			filters={"reference_doctype": "User", "reference_name": "Administrator"},
			fields=["notification_key"],
			order_by="creation desc",
			limit=1,
		)
		self.assertEqual(sms_queue[0].notification_key, "_Test Key")
