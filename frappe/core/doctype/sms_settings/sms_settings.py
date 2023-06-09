# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.utils import nowdate, cint, cstr
from frappe.model.document import Document
from frappe.core.doctype.notification_count.notification_count import add_notification_count, get_notification_count,\
	set_notification_last_scheduled
from six import string_types
from frappe.model.base_document import get_controller
import json


class SMSSettings(Document):
	pass


@frappe.whitelist()
def send_sms(receiver_list,
		message,
		success_msg=True,
		notification_type=None,
		reference_doctype=None,
		reference_name=None,
		party_doctype=None,
		party=None):

	notification_type = cstr(notification_type)

	receiver_list = clean_receiver_nos(receiver_list)

	args = frappe._dict({
		'receiver_list': receiver_list,
		'message': message,
		'success_msg': success_msg,
		'notification_type': notification_type,
		'reference_doctype': reference_doctype,
		'reference_name': reference_name,
		'party_doctype': party_doctype,
		'party': party,
	})

	create_communication(args)
	process_and_send(args)


def enqueue_template_sms(doc, notification_type=None, context=None, allow_if_already_sent=False, send_after=None):
	from frappe.core.doctype.sms_queue.sms_queue import queue_sms

	notification_type = cstr(notification_type)

	if not is_sms_enabled():
		return False

	if not is_automated_sms_enabled():
		return False

	validation = run_validate_notification(doc, notification_type, throw=False)
	if not validation:
		return False

	if not allow_if_already_sent:
		notification_count = get_notification_count(doc.doctype, doc.name, notification_type, "SMS")
		if notification_count:
			return False

	args = get_template_sms_args(notification_type, doc=doc, context=context, throw=False)
	if not args:
		return False

	if not args.get('receiver_list'):
		return False

	if send_after:
		args['send_after'] = send_after

	set_notification_last_scheduled(doc.doctype, doc.name, notification_type, "SMS")
	create_communication(args, automated=True)
	queue_sms(args)

	return True


def send_template_sms(notification_type, reference_doctype=None, reference_name=None, doc=None, context=None, receiver_list=None):
	args = get_template_sms_args(notification_type, reference_doctype=reference_doctype, reference_name=reference_name,
		doc=doc, context=context, get_doc=True, throw=True)

	if receiver_list:
		args['receiver_list'] = clean_receiver_nos(receiver_list)

	create_communication(args)
	process_and_send(args)


def get_template_sms_args(notification_type,
		reference_doctype=None, reference_name=None,
		doc=None, get_doc=False,
		context=None,
		is_automated_sms=True, throw=True
):
	from frappe.core.doctype.sms_template.sms_template import get_sms_template

	if not doc and reference_doctype and reference_name:
		doc = frappe.get_doc(reference_doctype, reference_name)

	if not doc:
		if throw:
			frappe.throw(_("Template SMS could not be generated because reference document not provided"))
		else:
			return None

	notification_type = cstr(notification_type)
	for_notification_type_str = " for Notification Type {0}".format(notification_type) if notification_type else ""

	args = get_sms_args_from_controller(notification_type, doc)
	if not args:
		if throw:
			frappe.throw(_("Template SMS not supported for {0}{1}")
				.format(args.reference_doctype, for_notification_type_str))
		else:
			return None

	args['receiver_list'] = clean_receiver_nos(args.get('receiver_list'))

	sms_template = get_sms_template(args.reference_doctype, notification_type)
	if not sms_template:
		if throw:
			frappe.throw(_("SMS Template not available for {0}{1}")
				.format(args.reference_doctype, for_notification_type_str))
		else:
			return None

	if is_automated_sms and not sms_template.allow_automated_sms:
		if throw:
			frappe.throw(_("{0} SMS Template not allowed for automated SMS").format(notification_type))
		else:
			return None

	message = sms_template.get_rendered_message(doc=doc, context=context)
	if not message:
		if throw:
			frappe.throw(_("SMS Message empty for {0} {1}{2}")
				.format(args.reference_doctype, args.reference_name, for_notification_type_str))
		else:
			return None

	args.update({
		'message': message,
		'notification_type': notification_type,
		'success_msg': args.get('success_msg') or True
	})

	if get_doc:
		args['doc'] = doc

	return args


def get_sms_args_from_controller(notification_type, doc):
	notification_type = cstr(notification_type)
	args = frappe._dict(doc.run_method("get_sms_args", notification_type=notification_type))
	if args:
		args.reference_doctype = doc.doctype
		args.reference_name = doc.name
		args.child_doctype = child_doctype
		args.child_name = child_name

	return args


def process_and_send(args):
	if not frappe.get_cached_value('SMS Settings', None, 'sms_gateway_url'):
		frappe.throw(_("Please Update SMS Settings"))

	args = frappe._dict(args)

	args['receiver_list'] = clean_receiver_nos(args.get('receiver_list'))
	if not args.get('receiver_list'):
		frappe.throw(_("No valid Mobile Number provided"))

	if not args.get('message'):
		frappe.throw(_("No SMS message provided"))

	args['message'] = frappe.safe_decode(args.get('message')).encode('utf-8')

	if not args.get('doc'):
		args['doc'] = get_doc_for_triggers(args.get('reference_doctype'), args.get('reference_name'))

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
			"communication_type": "Automated Message" if automated else "Communication",
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
	doc = args.get('doc')
	notification_type = cstr(args.get('notification_type'))

	if doc:
		validation = run_validate_notification(doc, notification_type, throw=True)
		if not validation:
			frappe.throw(_("{0} Notification Validation Failed").format(notification_type))


def run_validate_notification(doc, notification_type, throw=True):
	notification_type = cstr(notification_type)
	validation = doc.run_method("validate_notification", notification_type=notification_type, throw=throw)

	if validation is None:
		return True
	else:
		return cint(validation)


def run_after_send_methods(args):
	notification_type = cstr(args.get('notification_type'))
	if args.get("reference_doctype") and args.get("reference_name"):
		add_notification_count(args.get("reference_doctype"), args.get("reference_name"), notification_type, 'SMS')

	doc = args.get('doc')
	if doc:
		doc.run_method("after_send_notification", notification_medium="SMS", notification_type=notification_type)
		doc.notify_update()


def get_doc_for_triggers(reference_doctype, reference_name):
	if not reference_doctype or not reference_name:
		return

	try:
		controller = get_controller(reference_doctype)
		has_validate_notification = hasattr(controller, "validate_notification")
		has_after_send_notification = hasattr(controller, "after_send_notification")
		if has_validate_notification or has_after_send_notification:
			doc = frappe.get_doc(reference_doctype, reference_name)
			return doc
	except ImportError:
		pass


def send_via_gateway(args):
	ss = frappe.get_cached_doc('SMS Settings', None)
	headers = get_headers(ss)
	use_json = headers.get("Content-Type") == "application/json"

	request_params = {
		ss.message_parameter: args.get('message')
	}

	for d in ss.get("parameters"):
		if not d.header:
			request_params[d.parameter] = d.value

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
		sms_settings = frappe.get_doc("SMS Settings", "SMS Settings")

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
	response.raise_for_status()
	return response


def validate_response(response, sms_settings=None):
	if not sms_settings:
		sms_settings = frappe.get_doc('SMS Settings', 'SMS Settings')

	if not (200 <= response.status_code < 300):
		return False

	if sms_settings.response_validation:
		valid = frappe.safe_eval(sms_settings.response_validation, eval_locals={'response': response})
		if not valid:
			return False

	return True


def get_error_message(response, sms_settings=None):
	if not sms_settings:
		sms_settings = frappe.get_doc('SMS Settings', 'SMS Settings')

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


def clean_receiver_nos(receiver_list):
	if isinstance(receiver_list, string_types):
		receiver_list = json.loads(receiver_list)
		if not isinstance(receiver_list, list):
			receiver_list = [receiver_list]

	cleaned_receiver_list = []
	if not receiver_list:
		return cleaned_receiver_list

	invalid_characters = (' ', '\t', '-', '(', ')')

	for d in receiver_list:
		for char in invalid_characters:
			d = cstr(d).replace(char, '')

		if d:
			cleaned_receiver_list.append(d)

	return cleaned_receiver_list


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
