# Copyright (c) 2022, Frappe Technologies and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.core.doctype.sms_queue.sms_queue import clear_queue, get_queue, queue_sms, send_one
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

	def make_sms_queue(self, message, receiver_list=None, **kwargs):
		queue_sms(
			frappe._dict(
				receiver_list=receiver_list or ["+971501234567", "+971501234568"],
				message=message,
				notification_key="_Test Key",
				reference_doctype="User",
				reference_name="test@example.com",
				**kwargs,
			),
			delayed=True,
		)
		return frappe.get_last_doc("SMS Queue", {"message": message})

	def get_status(self, sms_queue):
		sms_queue.reload()
		return sms_queue.status, [d.status for d in sms_queue.recipients]

	@patch("frappe.are_sms_muted", return_value=False)
	@patch("frappe.core.doctype.sms_queue.sms_queue.process_and_send")
	def test_send_one(self, process_and_send, are_sms_muted):
		sms_queue = self.make_sms_queue("Test send one")
		send_one(sms_queue.name, auto_commit=False)

		self.assertEqual(self.get_status(sms_queue), ("Sent", ["Sent", "Sent"]))
		self.assertEqual(
			[call.args[0].receiver_list for call in process_and_send.call_args_list],
			[["+971501234567"], ["+971501234568"]],
		)
		sms_args = process_and_send.call_args.args[0]
		self.assertEqual(sms_args.sms_queue, sms_queue.name)
		self.assertEqual(sms_args.notification_key, "_Test Key")
		self.assertFalse(sms_args.success_msg)

		# a sent queue isn't sent again
		send_one(sms_queue.name, auto_commit=False)
		self.assertEqual(process_and_send.call_count, 2)

	@patch("frappe.are_sms_muted", return_value=False)
	@patch("frappe.core.doctype.sms_queue.sms_queue.process_and_send")
	def test_send_errors(self, process_and_send, are_sms_muted):
		process_and_send.side_effect = frappe.ValidationError("Gateway down")

		sms_queue = self.make_sms_queue("Test send error")
		send_one(sms_queue.name, auto_commit=False)
		self.assertEqual(self.get_status(sms_queue), ("Not Sent", ["Not Sent", "Not Sent"]))
		self.assertEqual(sms_queue.retry, 1)

		# after 3 retries the queue errors
		sms_queue.db_set("retry", 3)
		send_one(sms_queue.name, auto_commit=False)
		self.assertEqual(self.get_status(sms_queue), ("Error", ["Not Sent", "Not Sent"]))
		self.assertEqual(sms_queue.error, "Gateway down")

		process_and_send.side_effect = [None, frappe.ValidationError("Gateway down")]
		sms_queue = self.make_sms_queue("Test partial error")
		sms_queue.db_set("retry", 3)
		send_one(sms_queue.name, auto_commit=False)
		self.assertEqual(self.get_status(sms_queue), ("Partially Errored", ["Sent", "Not Sent"]))

	@patch("frappe.are_sms_muted", return_value=True)
	@patch("frappe.core.doctype.sms_queue.sms_queue.process_and_send")
	def test_muted(self, process_and_send, are_sms_muted):
		sms_queue = self.make_sms_queue("Test muted")
		send_one(sms_queue.name, auto_commit=False)

		process_and_send.assert_not_called()
		self.assertEqual(self.get_status(sms_queue), ("Not Sent", ["Not Sent", "Not Sent"]))

	def test_get_queue(self):
		later = self.make_sms_queue("Test later", send_after=add_days(now_datetime(), 1))
		low = self.make_sms_queue("Test low priority", priority=1)
		high = self.make_sms_queue("Test high priority", priority=5)

		queue = [d.name for d in get_queue()]
		self.assertNotIn(later.name, queue)
		self.assertLess(queue.index(high.name), queue.index(low.name))

	def test_clear_queue(self):
		old = self.make_sms_queue("Test old")
		stale = self.make_sms_queue("Test stale", priority=5)
		recent = self.make_sms_queue("Test recent")
		frappe.db.set_value(
			"SMS Queue", old.name, "modified", add_days(now_datetime(), -32), update_modified=False
		)
		frappe.db.set_value(
			"SMS Queue", stale.name, "modified", add_days(now_datetime(), -8), update_modified=False
		)

		clear_queue()

		self.assertFalse(frappe.db.exists("SMS Queue", old.name))
		self.assertFalse(frappe.db.exists("SMS Queue Recipient", {"parent": old.name}))
		self.assertEqual(frappe.db.get_value("SMS Queue", stale.name, "status"), "Expired")
		self.assertEqual(frappe.db.get_value("SMS Queue", recent.name, "status"), "Not Sent")

	def test_only_administrator_deletes(self):
		sms_queue = self.make_sms_queue("Test delete")
		frappe.set_user("test@example.com")
		self.addCleanup(frappe.set_user, "Administrator")
		self.assertRaises(frappe.ValidationError, sms_queue.on_trash)
