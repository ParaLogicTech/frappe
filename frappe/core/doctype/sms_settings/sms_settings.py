# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.utils import nowdate, cint, cstr
from frappe.model.document import Document
from frappe.core.doctype.notification_count.notification_count import add_notification_count
import json


class SMSSettings(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.core.doctype.sms_parameter.sms_parameter import SMSParameter
		from frappe.types import DF

		error_message: DF.Code | None
		message_parameter: DF.Data
		number_formatter: DF.Code | None
		parameters: DF.Table[SMSParameter]
		receiver_parameter: DF.Data
		response_validation: DF.Code | None
		sms_gateway_url: DF.SmallText
		use_post: DF.Check
	# end: auto-generated types
	pass


@frappe.whitelist()
def send_sms(
	receiver_list,
	message,
	success_msg=True,
	notification_type=None,
	reference_doctype=None,
	reference_name=None,
	child_doctype=None,
	child_name=None,
	party_doctype=None,
	party=None,
	is_promotional=False,
	queue=False,
	queue_separately=False,
	send_after=None,
	automated=False,
	priority=1,
):
	notification_type = cstr(notification_type)

	receiver_list = clean_receiver_nos(receiver_list, format_sms=True)

	args = frappe._dict({
		'receiver_list': receiver_list,
		'message': message,
		'success_msg': success_msg,
		'notification_type': notification_type,
		'reference_doctype': reference_doctype,
		'reference_name': reference_name,
		'child_doctype': child_doctype,
		'child_name': child_name,
		'party_doctype': party_doctype,
		'party': party,
		'is_promotional': cint(is_promotional),
		'priority': cint(priority),
	})

	queue = cint(queue)
	queue_separately = cint(queue_separately)
	if send_after:
		args['send_after'] = send_after
		queue = True

	create_communication(args, automated=automated)

	if queue:
		from frappe.core.doctype.sms_queue.sms_queue import queue_sms
		if queue_separately:
			for r in receiver_list:
				receiver_args = args.copy()
				receiver_args["communication"] = None
				receiver_args["receiver_list"] = [r]
				queue_sms(receiver_args, delayed=True)
		else:
			queue_sms(args)
	else:
		process_and_send(args)


def process_and_send(args):
	from frappe.email.doctype.notification.notification import get_doc_for_notification_triggers

	if not frappe.get_cached_value('SMS Settings', None, 'sms_gateway_url'):
		frappe.throw(_("Please Update SMS Settings"))

	args = frappe._dict(args)

	args['receiver_list'] = clean_receiver_nos(args.get('receiver_list'), format_sms=True)
	if not args.get('receiver_list'):
		frappe.throw(_("No valid Mobile Number provided"))

	if not args.get('message'):
		frappe.throw(_("No SMS message provided"))

	args['message'] = frappe.safe_decode(args.get('message')).encode('utf-8')

	if not args.get('doc'):
		args['doc'] = get_doc_for_notification_triggers(args.get('reference_doctype'), args.get('reference_name'))

	run_before_send_methods(args)
	send_via_gateway(args)
	run_after_send_methods(args)


def create_communication(args, automated=False):
	"""Make communication entry"""
	if args.get('reference_doctype') and args.get('reference_name'):
		subject = "SMS"
		if args.get('subject') or args.get('notification_type'):
			subject = "{0} SMS".format(args.get('subject') or args.get('notification_type'))

		receiver_list = args.get('receiver_list') or []

		comm = frappe.get_doc({
			"doctype": "Communication",
			"communication_medium": "SMS",
			"communication_type": "Automated Message" if cint(automated) else "Communication",
			"subject": subject or 'SMS',
			"content": args.get('message'),
			"sent_or_received": "Sent",
			"reference_doctype": args.get('reference_doctype'),
			"reference_name": args.get('reference_name'),
			"sender": frappe.session.user,
			"recipients": "\n".join(receiver_list),
			"phone_no": receiver_list[0] if len(receiver_list) == 1 else None
		})

		if args.get('party_doctype') and args.get('party'):
			comm.append("timeline_links", {
				"link_doctype": args.get('party_doctype'),
				"link_name": args.get('party')
			})

		comm.insert(ignore_permissions=True)
		args['communication'] = comm.name


def run_before_send_methods(args):
	from frappe.email.doctype.notification.notification import run_validate_notification

	doc = args.get('doc')
	notification_type = cstr(args.get('notification_type'))

	if doc and notification_type:
		validation = run_validate_notification(
			doc, notification_type, child_doctype=args.get("child_doctype"), child_name=args.get("child_name"), throw=True
		)
		if not validation:
			frappe.throw(_("{0} Notification Validation Failed").format(notification_type))


def run_after_send_methods(args):
	notification_type = cstr(args.get('notification_type'))
	if args.get("reference_doctype") and args.get("reference_name") and notification_type:
		add_notification_count(args.get("reference_doctype"), args.get("reference_name"), notification_type, 'SMS',
			child_doctype=args.get("child_doctype"), child_name=args.get("child_name"))


def send_via_gateway(args):
	ss = frappe.get_cached_doc('SMS Settings', None)
	headers = get_headers(ss)
	use_json = headers.get("Content-Type") == "application/json"

	request_params = {
		ss.message_parameter: args.get('message')
	}

	for d in ss.get("parameters"):
		if d.header:
			continue
		if d.promotional and not args.get("is_promotional"):
			continue

		request_params[d.parameter] = d.value

	frappe.utils.call_hook_method("update_sms_request_params",
		params=request_params, headers=headers, args=args)

	success_list = []
	fail_list = []
	for d in args.get('receiver_list'):
		request_params[ss.receiver_parameter] = d
		response = send_request(ss.sms_gateway_url, request_params, headers, ss.use_post)

		if validate_response(response, ss):
			success_list.append(d)
		else:
			fail_list.append({'number': d, 'error': get_error_message(response, ss)})

	fail_message_list = ["{0} ({1})".format(d.get('number'), d.get('error') or 'Unknown Error') for d in fail_list]

	if len(success_list) > 0:
		create_sms_log(args, success_list)
		if args.get('success_msg'):
			frappe.msgprint(_("SMS sent to the following numbers:<br>{0}").format("<br>".join(success_list)))
			if fail_message_list:
				frappe.msgprint(_("SMS failed for the following numbers:<br>{0}").format("<br>".join(fail_message_list)))
	else:
		frappe.throw(_("SMS could not be sent{0}").format("<br>{0}".format(fail_message_list[0]) if fail_message_list else ""))


def get_headers(sms_settings=None):
	if not sms_settings:
		sms_settings = frappe.get_cached_doc("SMS Settings", None)

	headers = {"Accept": "text/plain, text/html, */*"}
	for d in sms_settings.get("parameters"):
		if d.header == 1:
			headers.update({d.parameter: d.value})

	return headers


def send_request(gateway_url, params, headers=None, use_post=False, use_json=False):
	import requests

	if not headers:
		headers = get_headers()
	kwargs = {"headers": headers}

	if use_json:
		kwargs["json"] = params
	elif use_post:
		kwargs["data"] = params
	else:
		kwargs["params"] = params

	if use_post:
		response = requests.post(gateway_url, **kwargs)
	else:
		response = requests.get(gateway_url, **kwargs)

	return response


def validate_response(response, sms_settings=None):
	import requests

	if not sms_settings:
		sms_settings = frappe.get_cached_doc("SMS Settings", None)

	if not (200 <= response.status_code < 300):
		return False

	try:
		response.raise_for_status()
	except requests.exceptions.HTTPError:
		return False

	if sms_settings.response_validation:
		valid = frappe.safe_eval(sms_settings.response_validation, eval_locals={'response': response})
		if not valid:
			return False

	return True


def get_error_message(response, sms_settings=None):
	if not sms_settings:
		sms_settings = frappe.get_cached_doc("SMS Settings", None)

	if sms_settings.error_message:
		return frappe.safe_eval(sms_settings.error_message, eval_locals={'response': response})


def is_sms_enabled():
	return True if frappe.get_cached_value('SMS Settings', None, 'sms_gateway_url') else False


def is_automated_sms_enabled():
	if not is_sms_enabled():
		return False

	return cint(frappe.conf.get('enable_automated_sms'))


# Create SMS Log
# =========================================================
def create_sms_log(args, sent_to):
	if args.get("sms_log_message"):
		message = args.get("sms_log_message")
	else:
		message = args['message'].decode('utf-8')

	sl = frappe.new_doc('SMS Log')
	sl.sent_on = frappe.utils.now_datetime()
	sl.message = message
	sl.no_of_requested_sms = len(args['receiver_list'])
	sl.requested_numbers = "\n".join(args['receiver_list'])
	sl.no_of_sent_sms = len(sent_to)
	sl.sent_to = "\n".join(sent_to)
	sl.reference_doctype = args.get('reference_doctype')
	sl.reference_name = args.get('reference_name')
	sl.communication = args.get('communication')
	sl.flags.ignore_permissions = True
	sl.save()

	if args.get('communication') and not args.get('sms_queue'):
		frappe.get_doc('Communication', args.get('communication')).set_delivery_status(commit=False)


def clean_receiver_nos(receiver_list, format_sms=False):
	if isinstance(receiver_list, str):
		receiver_list = json.loads(receiver_list)
		if not isinstance(receiver_list, list):
			receiver_list = [receiver_list]

	cleaned_receiver_list = []
	if not receiver_list:
		return cleaned_receiver_list

	for number in receiver_list:
		number = clean_receiver_number(number, format_sms=format_sms)
		if number:
			cleaned_receiver_list.append(number)

	return cleaned_receiver_list


def clean_receiver_number(number, format_sms=False):
	number = clean_phone_no(number)

	if format_sms:
		sms_settings = frappe.get_cached_doc("SMS Settings", None)
		if sms_settings.number_formatter:
			formatted_number = frappe.safe_eval(sms_settings.number_formatter, eval_locals={'number': number})
			if formatted_number:
				number = formatted_number

	return number


def clean_phone_no(number):
	invalid_characters = {' ', '\t', '-', '(', ')', '\xa0'}
	number = "".join([c for c in cstr(number) if c not in invalid_characters])
	return number


@frappe.whitelist()
def get_contact_number(contact_name=None, ref_doctype=None, ref_name=None):
	mobile_no = None
	if contact_name:
		mobile_no = frappe.db.get_value("Contact", contact_name, "mobile_no")

	if not mobile_no and ref_doctype and ref_name:
		number = frappe.db.sql_list("""
			select c.mobile_no
			from `tabContact` c
			where ifnull(c.mobile_no, '') != ''
				and exists(select dl.name from `tabDynamic Link` dl where dl.parenttype = 'Contact' and dl.parent = c.name
					and link_doctype=%s and link_name=%s)
			limit 1
		""", (ref_doctype, ref_name))

		if number:
			mobile_no = number[0]

	return mobile_no or ''
