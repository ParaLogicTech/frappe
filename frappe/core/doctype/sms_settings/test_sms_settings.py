# Copyright (c) 2017, Frappe Technologies and Contributors
# License: MIT. See LICENSE
from unittest.mock import patch

import requests

import frappe
from frappe.core.doctype.notification_count.notification_count import get_notification_count
from frappe.core.doctype.sms_settings.sms_settings import (
	check_sms_permission,
	clean_receiver_nos,
	get_contact_number,
	process_and_send,
	queue_or_send_sms,
	send_sms,
	send_via_gateway,
)
from frappe.tests.utils import FrappeTestCase


def make_response(status_code=200, text="OK"):
	response = requests.Response()
	response.status_code = status_code
	response._content = text.encode()
	return response


SETTINGS_FIELDS = (
	"sms_gateway_url",
	"message_parameter",
	"receiver_parameter",
	"parameters",
	"use_post",
	"response_validation",
	"error_message",
	"number_formatter",
	"allowed_roles",
)


class TestSMSSettings(FrappeTestCase):
	def setUp(self):
		frappe.db.set_single_value("SMS Settings", "sms_gateway_url", "https://sms.example.com/send")
		self.sms_settings = frappe.get_single("SMS Settings")
		self._allowed_roles = self.sms_settings.get("allowed_roles")
		self.sms_settings.set("allowed_roles", [])
		self.sms_settings.flags.ignore_mandatory = True
		self.sms_settings.save()

	def tearDown(self):
		frappe.set_user("Administrator")
		self.sms_settings.set("allowed_roles", self._allowed_roles)
		self.sms_settings.flags.ignore_mandatory = True
		self.sms_settings.save()

	def test_user_without_allowed_role_is_blocked(self):
		frappe.set_user("test@example.com")
		self.assertRaises(frappe.PermissionError, check_sms_permission)

	def test_system_manager_is_always_allowed(self):
		frappe.set_user("Administrator")
		check_sms_permission()

	def test_user_with_configured_role_is_allowed(self):
		self.sms_settings.append("allowed_roles", {"role": "System Manager"})
		self.sms_settings.flags.ignore_mandatory = True
		self.sms_settings.save()

		frappe.set_user("test@example.com")
		frappe.get_doc(
			{
				"doctype": "Has Role",
				"parent": "test@example.com",
				"parenttype": "User",
				"parentfield": "roles",
				"role": "System Manager",
			}
		).db_insert()
		frappe.clear_cache(user="test@example.com")

		check_sms_permission()

		frappe.db.delete("Has Role", {"parent": "test@example.com", "role": "System Manager"})
		frappe.clear_cache(user="test@example.com")

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


class TestSMSSending(FrappeTestCase):
	def setUp(self):
		sms_settings = frappe.get_single("SMS Settings")
		self.original_settings = {}
		for fieldname in SETTINGS_FIELDS:
			value = sms_settings.get(fieldname)
			if isinstance(value, list):
				value = [d.as_dict(no_default_fields=True) for d in value]
			self.original_settings[fieldname] = value

		self.update_settings(sms_gateway_url="https://sms.example.com/send")

	def tearDown(self):
		frappe.set_user("Administrator")
		self.update_settings(**self.original_settings)

	def update_settings(self, **values):
		sms_settings = frappe.get_single("SMS Settings")
		sms_settings.update(values)
		sms_settings.flags.ignore_mandatory = True
		sms_settings.save()

	def configure_gateway(self, **settings):
		self.update_settings(
			**{
				"message_parameter": "msg",
				"receiver_parameter": "to",
				"parameters": [
					{"parameter": "api_key", "value": "_test_key"},
					{"parameter": "Authorization", "value": "Bearer _test_token", "header": 1},
					{"parameter": "mask", "value": "_Test Brand", "promotional": 1},
				],
				**settings,
			}
		)

	def get_sms_args(self, **kwargs):
		return {
			"receiver_list": ["+971501234567"],
			"message": "Test SMS",
			"reference_doctype": "User",
			"reference_name": "test@example.com",
			**kwargs,
		}

	def test_send_sms_api_checks_allowed_roles(self):
		user = frappe.get_doc(
			doctype="User",
			email="_test_sms_sender@example.com",
			first_name="SMS Sender",
			send_welcome_email=0,
		).insert(ignore_if_duplicate=True)
		user.add_roles("Blogger")
		frappe.set_user(user.name)

		with patch("frappe.core.doctype.sms_settings.sms_settings.queue_or_send_sms") as queue_or_send:
			self.assertRaises(frappe.PermissionError, send_sms, ["+971501234567"], "Test")
		queue_or_send.assert_not_called()

		frappe.set_user("Administrator")
		self.update_settings(allowed_roles=[{"role": "Blogger"}])
		frappe.set_user(user.name)
		with patch("frappe.core.doctype.sms_settings.sms_settings.queue_or_send_sms") as queue_or_send:
			send_sms(["+971501234567"], "Test")
		queue_or_send.assert_called_once()

	def get_communication(self, name):
		return frappe.get_doc("Communication", name)

	@patch("frappe.core.doctype.sms_settings.sms_settings.send_via_gateway")
	def test_send_now_creates_communication(self, send_via_gateway):
		queue_or_send_sms(
			receiver_list=["+971 50-123 4567"],
			message="Test send now",
			notification_key="_Test Key",
			reference_doctype="User",
			reference_name="test@example.com",
			party_doctype="User",
			party="test@example.com",
		)

		sms_args = send_via_gateway.call_args.args[0]
		self.assertEqual(sms_args.receiver_list, ["+971501234567"])
		self.assertEqual(sms_args.message, b"Test send now")

		communication = self.get_communication(sms_args.communication)
		self.assertEqual(communication.communication_medium, "SMS")
		self.assertEqual(communication.communication_type, "Communication")
		self.assertEqual(communication.subject, "_Test Key SMS")
		self.assertEqual(communication.phone_no, "+971501234567")
		self.assertIn(
			("User", "test@example.com"),
			[(d.link_doctype, d.link_name) for d in communication.timeline_links],
		)

	@patch("frappe.core.doctype.sms_settings.sms_settings.send_via_gateway")
	def test_automated_communication(self, send_via_gateway):
		queue_or_send_sms(
			receiver_list=["+971501234567", "+971501234568"],
			message="Test automated",
			reference_doctype="User",
			reference_name="test@example.com",
			automated=True,
		)

		communication = self.get_communication(send_via_gateway.call_args.args[0].communication)
		self.assertEqual(communication.communication_type, "Automated Message")
		self.assertEqual(communication.subject, "SMS")
		self.assertEqual(communication.recipients, "+971501234567\n+971501234568")
		self.assertFalse(communication.phone_no)

		# no communication without a reference document
		queue_or_send_sms(receiver_list=["+971501234567"], message="Test without reference")
		self.assertFalse(send_via_gateway.call_args.args[0].get("communication"))

	def get_sms_queues(self, message):
		return frappe.get_all(
			"SMS Queue",
			filters={"message": message},
			fields=["name", "send_after", "communication", "notification_key"],
		)

	@patch("frappe.core.doctype.sms_settings.sms_settings.send_via_gateway")
	def test_queue(self, send_via_gateway):
		queue_or_send_sms(
			receiver_list=["+971501234567", "+971501234568"],
			message="Test queue",
			notification_key="_Test Key",
			reference_doctype="User",
			reference_name="test@example.com",
			queue=True,
		)
		queues = self.get_sms_queues("Test queue")
		self.assertEqual(len(queues), 1)
		self.assertTrue(queues[0].communication)
		self.assertEqual(queues[0].notification_key, "_Test Key")
		self.assertEqual(
			frappe.get_all(
				"SMS Queue Recipient", {"parent": queues[0].name}, pluck="recipient", order_by="idx"
			),
			["+971501234567", "+971501234568"],
		)

		# send_after queues even without queue=True
		queue_or_send_sms(
			receiver_list=["+971501234567"], message="Test send after", send_after="2099-01-01 10:00:00"
		)
		queues = self.get_sms_queues("Test send after")
		self.assertEqual(len(queues), 1)
		self.assertEqual(str(queues[0].send_after), "2099-01-01 10:00:00")

		queue_or_send_sms(
			receiver_list=["+971501234567", "+971501234568"],
			message="Test queue separately",
			reference_doctype="User",
			reference_name="test@example.com",
			queue=True,
			queue_separately=True,
		)
		self.assertEqual(len(self.get_sms_queues("Test queue separately")), 2)

		send_via_gateway.assert_not_called()

	@patch("frappe.core.doctype.sms_settings.sms_settings.send_request", return_value=make_response())
	def test_gateway_request(self, send_request):
		self.configure_gateway()
		sms_args = frappe._dict(
			receiver_list=["+971501234567", "+971501234568"],
			message=b"Test gateway",
			reference_doctype="User",
			reference_name="test@example.com",
		)
		send_via_gateway(sms_args)

		self.assertEqual(send_request.call_count, 2)
		url, params, headers = send_request.call_args.args
		self.assertEqual(url, "https://sms.example.com/send")
		self.assertEqual(params, {"msg": b"Test gateway", "api_key": "_test_key", "to": "+971501234568"})
		self.assertEqual(headers["Authorization"], "Bearer _test_token")
		self.assertEqual(send_request.call_args.kwargs, {"use_post": 0, "use_json": False})

		sms_log = frappe.get_last_doc("SMS Log", {"reference_name": "test@example.com"})
		self.assertEqual(sms_log.message, "Test gateway")
		self.assertEqual(sms_log.sent_to, "+971501234567\n+971501234568")
		self.assertEqual(sms_log.no_of_sent_sms, 2)

		# promotional SMS get the promotional parameters, a JSON header sends JSON
		self.configure_gateway(use_post=1)
		sms_settings = frappe.get_single("SMS Settings")
		sms_settings.append(
			"parameters", {"parameter": "Content-Type", "value": "application/json", "header": 1}
		)
		self.update_settings(parameters=sms_settings.parameters)
		send_via_gateway(frappe._dict(receiver_list=["+971501234567"], message=b"Test", is_promotional=1))

		_url, params, _headers = send_request.call_args.args
		self.assertEqual(params["mask"], "_Test Brand")
		self.assertEqual(send_request.call_args.kwargs, {"use_post": 1, "use_json": True})

	@patch("frappe.core.doctype.sms_settings.sms_settings.send_request")
	def test_gateway_failures(self, send_request):
		self.configure_gateway(response_validation="response.text == 'OK'", error_message="response.text")

		# a 200 response that fails the response validation counts as failed
		send_request.side_effect = [make_response(), make_response(200, "Invalid number")]
		send_via_gateway(
			frappe._dict(
				receiver_list=["+971501234567", "+971501234568"],
				message=b"Test partial",
				reference_name="_Test Partial",
				success_msg=True,
			)
		)
		sms_log = frappe.get_last_doc("SMS Log", {"reference_name": "_Test Partial"})
		self.assertEqual(sms_log.sent_to, "+971501234567")
		self.assertEqual(sms_log.no_of_requested_sms, 2)
		self.assertIn("+971501234568 (Invalid number)", frappe.message_log[-1].get("message"))

		send_request.side_effect = [make_response(500, "Server error")]
		with self.assertRaisesRegex(frappe.ValidationError, "Server error"):
			send_via_gateway(frappe._dict(receiver_list=["+971501234567"], message=b"Test failed"))

	def test_clean_receiver_nos(self):
		self.assertEqual(
			clean_receiver_nos(["+971 50-123 4567", "(050) 1234567\xa0", ""]), ["+971501234567", "0501234567"]
		)
		self.assertEqual(clean_receiver_nos('["+971501234567"]'), ["+971501234567"])
		self.assertEqual(clean_receiver_nos('"+971501234567"'), ["+971501234567"])
		self.assertEqual(clean_receiver_nos(None), [])

		self.configure_gateway(number_formatter="number.replace('+', '00')")
		self.assertEqual(clean_receiver_nos(["+971501234567"], format_sms=True), ["00971501234567"])
		self.assertEqual(clean_receiver_nos(["+971501234567"]), ["+971501234567"])

	@patch("frappe.core.doctype.sms_settings.sms_settings.send_via_gateway")
	def test_process_and_send_errors(self, send_via_gateway):
		self.assertRaisesRegex(
			frappe.ValidationError,
			"No valid Mobile Number",
			process_and_send,
			self.get_sms_args(receiver_list=[" "]),
		)
		self.assertRaisesRegex(
			frappe.ValidationError, "No SMS message", process_and_send, self.get_sms_args(message="")
		)

		self.update_settings(sms_gateway_url="")
		self.assertRaisesRegex(
			frappe.ValidationError, "Please Update SMS Settings", process_and_send, self.get_sms_args()
		)
		send_via_gateway.assert_not_called()

	def test_get_contact_number(self):
		contact = frappe.get_doc(
			doctype="Contact",
			first_name="_Test SMS Contact",
			mobile_no="+971501234567",
			links=[{"link_doctype": "User", "link_name": "test@example.com"}],
		).insert()

		self.assertEqual(get_contact_number(contact.name), "+971501234567")
		self.assertEqual(get_contact_number(ref_doctype="User", ref_name="test@example.com"), "+971501234567")
		self.assertEqual(get_contact_number(ref_doctype="User", ref_name="test1@example.com"), "")
