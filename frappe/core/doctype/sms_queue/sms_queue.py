# -*- coding: utf-8 -*-
# Copyright (c) 2022, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import now_datetime
from frappe.model.document import Document
from frappe.core.doctype.sms_settings.sms_settings import process_and_send
from six import text_type


class SMSQueue(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.core.doctype.sms_queue_recipient.sms_queue_recipient import SMSQueueRecipient
		from frappe.types import DF

		child_doctype: DF.Link | None
		child_name: DF.Data | None
		communication: DF.Link | None
		error: DF.SmallText | None
		is_promotional: DF.Check
		message: DF.SmallText | None
		notification_type: DF.Data | None
		party: DF.DynamicLink | None
		party_doctype: DF.Link | None
		priority: DF.Int
		recipients: DF.Table[SMSQueueRecipient]
		reference_doctype: DF.Link | None
		reference_name: DF.Data | None
		retry: DF.Int
		send_after: DF.Datetime | None
		sender: DF.Data | None
		status: DF.Literal["Not Sent", "Sending", "Partially Sent", "Partially Errored", "Sent", "Error", "Expired"]
	# end: auto-generated types
	def on_trash(self):
		if frappe.session.user != 'Administrator':
			frappe.throw(_('Only Administrator can delete SMS Queue'))


def queue_sms(args, delayed=False, now=False):
	if not args.get('receiver_list'):
		return

	doc = frappe.new_doc("SMS Queue")
	for r in args.get('receiver_list'):
		doc.append("recipients", {'recipient': r})

	del args['receiver_list']
	doc.update(args)
	doc.insert(ignore_permissions=True)

	if not delayed and not doc.get('send_after'):
		if now:
			send_one(doc.name, now=now, auto_commit=not now)
		else:
			frappe.enqueue("frappe.core.doctype.sms_queue.sms_queue.send_one",
				sms_queue=doc.name, enqueue_after_commit=True)


def flush(from_test=False):
	"""flush SMS Queue, every time: called from scheduler"""

	auto_commit = not from_test
	if frappe.are_sms_muted():
		frappe.msgprint(_("SMS are muted"))
		return

	for sms_queue in get_queue():
		if sms_queue.name:
			send_one(sms_queue.name, auto_commit, from_test=from_test)


def send_one(sms_queue, auto_commit=True, now=False, from_test=False):
	if frappe.are_sms_muted():
		frappe.msgprint(_("SMS are muted"))
		return

	sms_queue = frappe.db.sql('''
		select name, status, message, sender, reference_doctype, reference_name, retry, party_doctype, party,
			child_doctype, child_name, notification_type, communication
		from `tabSMS Queue`
		where name = %s
		for update
	''', sms_queue, as_dict=True)[0]

	if sms_queue.status not in ('Not Sent', 'Partially Sent'):
		# rollback to release lock and return
		if auto_commit:
			frappe.db.rollback()
		return

	recipients_list = frappe.db.sql("""
		select name, recipient, status
		from `tabSMS Queue Recipient`
		where parent = %s
		order by idx
	""", sms_queue.name, as_dict=1)

	frappe.db.sql("""
		update `tabSMS Queue` set status='Sending', modified=%s where name=%s
	""", (now_datetime(), sms_queue.name), auto_commit=auto_commit)

	if sms_queue.communication:
		frappe.get_doc('Communication', sms_queue.communication).set_delivery_status(commit=auto_commit)

	try:
		for recipient in recipients_list:
			if recipient.status != "Not Sent":
				continue

			sms_args = prepare_sms(sms_queue, recipient.recipient)
			process_and_send(sms_args)

			recipient.status = "Sent"
			frappe.db.sql("""update `tabSMS Queue Recipient` set status='Sent', modified=%s where name=%s""",
				(now_datetime(), recipient.name), auto_commit=auto_commit)

		sms_sent_to_any_recipient = any(s.status == "Sent" for s in recipients_list)
		sms_sent_to_all_recipients = all(s.status == "Sent" for s in recipients_list)

		# if all are sent set status
		if sms_sent_to_all_recipients:
			frappe.db.sql("""update `tabSMS Queue` set status='Sent', modified=%s where name=%s""",
				(now_datetime(), sms_queue.name), auto_commit=auto_commit)
		elif sms_sent_to_any_recipient:
			frappe.db.sql("""update `tabSMS Queue` set status='Partially Sent', modified=%s where name=%s""",
				(now_datetime(), sms_queue.name), auto_commit=auto_commit)
		else:
			frappe.db.sql("""update `tabSMS Queue` set status='Error', error=%s
				where name=%s""", ("No valid recipients to send to", sms_queue.name), auto_commit=auto_commit)

		if sms_queue.communication:
			frappe.get_doc('Communication', sms_queue.communication).set_delivery_status(commit=auto_commit)

	except Exception as e:
		handle_error(e, sms_queue, recipients_list, auto_commit, now)


def handle_error(e, sms_queue, recipients_list, auto_commit, now):
	if auto_commit:
		frappe.db.rollback()

	sms_sent_to_any_recipient = any(s.status == "Sent" for s in recipients_list)

	if sms_queue.retry < 3:
		frappe.db.sql("""
			update `tabSMS Queue` set status='Not Sent', modified=%s, retry=retry+1 where name=%s
		""", (now_datetime(), sms_queue.name), auto_commit=auto_commit)
	else:
		if sms_sent_to_any_recipient:
			frappe.db.sql("""
				update `tabSMS Queue` set status='Partially Errored', error=%s where name=%s
			""", (text_type(e), sms_queue.name), auto_commit=auto_commit)
		else:
			frappe.db.sql("""update `tabSMS Queue` set status='Error', error=%s
				where name=%s""", (text_type(e), sms_queue.name), auto_commit=auto_commit)

	if sms_queue.communication:
		frappe.get_doc('Communication', sms_queue.communication).set_delivery_status(commit=auto_commit)

	if now:
		print(frappe.get_traceback())
		raise e
	else:
		frappe.log_error(
			title=_("Failed to send SMS"),
			reference_doctype="SMS Queue",
			reference_name=sms_queue.name
		)


def get_queue():
	return frappe.db.sql('''select
			name, sender
		from
			`tabSMS Queue`
		where
			(status='Not Sent' or status='Partially Sent') and
			(send_after is null or send_after < %(now)s)
		order
			by priority desc, creation asc
		limit 500''', { 'now': now_datetime() }, as_dict=True)


def prepare_sms(sms_queue, recipient):
	args = frappe._dict({
		'receiver_list': [recipient],
		'message': sms_queue.message,
		'success_msg': False,
		'notification_type': sms_queue.notification_type,
		'reference_doctype': sms_queue.reference_doctype,
		'reference_name': sms_queue.reference_name,
		'party_doctype': sms_queue.party_doctype,
		'party': sms_queue.party,
		'sms_queue': sms_queue.name,
		'child_doctype': sms_queue.child_doctype,
		'child_name': sms_queue.child_name,
		'is_promotional': sms_queue.is_promotional,
	})

	return args


def on_doctype_update():
	frappe.db.add_index('SMS Queue', ('status', 'send_after', 'priority', 'creation'), 'index_bulk_flush')


def clear_queue():
	"""Remove low priority older than 31 days in Outbox and expire SMS not sent for 7 days.
	Called daily via scheduler.
	Note: Used separate query to avoid deadlock
	"""

	sms_queues = frappe.db.sql_list("""
		SELECT `name`
		FROM `tabSMS Queue`
		WHERE `priority` <= 1 AND `modified` < (NOW() - INTERVAL '31' DAY)
	""")

	if sms_queues:
		frappe.db.sql("""DELETE FROM `tabSMS Queue` WHERE `name` IN %s""", [sms_queues])
		frappe.db.sql("""DELETE FROM `tabSMS Queue Recipient` WHERE `parent` IN %s""", [sms_queues])

	frappe.db.sql("""
		UPDATE `tabSMS Queue`
		SET `status`='Expired'
		WHERE `modified` < (NOW() - INTERVAL '7' DAY)
		AND `status`='Not Sent'
		AND (`send_after` IS NULL OR `send_after` < %(now)s)
	""", {'now': now_datetime()})
