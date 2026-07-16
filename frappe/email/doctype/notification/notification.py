# Copyright (c) 2018, Frappe Technologies and contributors
# License: MIT. See LICENSE

import json
import os
from collections import namedtuple

import frappe
from frappe import _
from frappe.core.doctype.role.role import get_info_based_on_role, get_user_info
from frappe.core.doctype.sms_settings.sms_settings import send_sms, clean_receiver_nos
from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification
from frappe.integrations.doctype.slack_webhook_url.slack_webhook_url import send_slack_message
from frappe.model.document import Document
from frappe.modules.utils import export_module_json, get_doc_module
from frappe.utils import add_to_date, cast, nowdate, validate_email_address, cstr, cint
from frappe.utils.jinja import validate_template
from frappe.utils.safe_exec import get_safe_globals
from frappe.core.doctype.notification_count.notification_count import (
	get_notification_last_scheduled, set_notification_last_scheduled
)
from frappe.model.base_document import get_controller

FORMATS = {"HTML": ".html", "Markdown": ".md", "Plain Text": ".txt"}
FORBIDDEN_DOCUMENT_TYPES = frozenset(("Email Queue", "SMS Queue",))
DATE_BASED_EVENTS = frozenset(("Days Before", "Days After"))


class Notification(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.email.doctype.notification_recipient.notification_recipient import NotificationRecipient
		from frappe.types import DF

		attach_files: DF.Literal["", "From Field", "All"]
		attach_print: DF.Check
		channel: DF.Literal["Email", "Slack", "System Notification", "SMS"]
		condition: DF.Code | None
		date_changed: DF.Literal[None]
		days_in_advance: DF.Int
		document_type: DF.Link
		email_template: DF.Link | None
		enabled: DF.Check
		event: DF.Literal["", "New", "Save", "Submit", "Cancel", "Days After", "Days Before", "Value Change", "Method", "Custom"]
		from_attach_field: DF.Literal[None]
		is_standard: DF.Check
		message: DF.Code | None
		message_type: DF.Literal["Markdown", "HTML", "Plain Text"]
		method: DF.Data | None
		module: DF.Link | None
		notification_type: DF.Data | None
		print_format: DF.Link | None
		property_value: DF.Data | None
		recipients: DF.Table[NotificationRecipient]
		send_only_once: DF.Check
		send_system_notification: DF.Check
		send_to_all_assignees: DF.Check
		sender: DF.Link | None
		sender_email: DF.Data | None
		set_property_after_alert: DF.Literal[None]
		slack_webhook_url: DF.Link | None
		subject: DF.Data | None
		timeline_field: DF.Data | None
		use_email_template: DF.Check
		value_changed: DF.Literal[None]
		with_container: DF.Check
	# end: auto-generated types

	def onload(self):
		"""load message"""
		if self.is_standard:
			self.message = self.get_template() or self.message

	def autoname(self):
		if not self.name:
			self.name = self.subject

	def validate(self):
		if self.channel in ("Email", "Slack", "System Notification"):
			validate_template(self.subject)

		validate_template(self.message)

		if self.event in ("Days Before", "Days After") and not self.date_changed:
			frappe.throw(_("Please specify which date field must be checked"))

		if self.event == "Value Change" and not self.value_changed:
			frappe.throw(_("Please specify which value field must be checked"))

		if self.attach_files == "From Field" and not self.from_attach_field:
			frappe.throw(_("Please specify the field from which to attach files"))

		self.validate_forbidden_document_types()
		self.validate_condition()
		self.validate_standard()
		frappe.cache.hdel("notifications", self.document_type)

	def on_update(self):
		frappe.cache.hdel("notifications", self.document_type)
		path = export_module_json(self, self.is_standard, self.module)
		if path and self.message:
			extension = FORMATS.get(self.message_type, ".md")
			file_path = path + extension
			with open(file_path, "w") as f:
				f.write(self.message)

			# py
			if not os.path.exists(path + ".py"):
				with open(path + ".py", "w") as f:
					f.write(
						"""import frappe

def get_context(context):
	# do your magic here
	pass
"""
					)

	def validate_standard(self):
		if self.is_standard and self.enabled and not frappe.conf.developer_mode:
			frappe.throw(
				_("Cannot edit Standard Notification. To edit, please disable this and duplicate it")
			)

	def validate_condition(self):
		temp_doc = frappe.new_doc(self.document_type)
		if self.condition:
			try:
				frappe.safe_eval(self.condition, get_safe_globals(), get_context(temp_doc.as_dict()))
			except Exception:
				frappe.throw(_("The Condition '{0}' is invalid").format(self.condition))

	def validate_forbidden_document_types(self):
		if self.document_type in FORBIDDEN_DOCUMENT_TYPES or (
			frappe.get_meta(self.document_type).istable and self.event not in DATE_BASED_EVENTS
		):
			# only date based events are allowed for child tables
			frappe.throw(
				_("Cannot set Notification with event {0} on Document Type {1}").format(
					_(self.event), _(self.document_type)
				)
			)

	def get_documents_for_today(self):
		"""get list of documents that will be triggered today"""
		docs = []

		diff_days = self.days_in_advance
		if self.event == "Days After":
			diff_days = -diff_days

		reference_date = add_to_date(nowdate(), days=diff_days)
		reference_date_start = reference_date + " 00:00:00.000000"
		reference_date_end = reference_date + " 23:59:59.000000"

		doc_list = frappe.get_all(
			self.document_type,
			fields="name",
			filters=[
				{self.date_changed: (">=", reference_date_start)},
				{self.date_changed: ("<=", reference_date_end)},
			],
		)

		eval_globals = get_safe_globals()
		for d in doc_list:
			doc = frappe.get_doc(self.document_type, d.name)

			if self.condition and not frappe.safe_eval(self.condition, eval_globals, get_context(doc)):
				continue

			docs.append(doc)

		return docs

	def send(self, doc, context=None):
		"""Build recipients and send Notification"""

		# context = get_context(doc)
		if not context:
			context = {}

		context.update({"doc": doc, "alert": self, "comments": None})
		if doc.get("_comments"):
			context["comments"] = json.loads(doc.get("_comments"))

		if self.is_standard:
			self.load_standard_properties(context)

		self.send_notification_by_channel(doc, context)

		if self.set_property_after_alert:
			allow_update = True
			if (
				doc.docstatus.is_submitted()
				and not doc.meta.get_field(self.set_property_after_alert).allow_on_submit
			):
				allow_update = False
			try:
				if allow_update and not doc.flags.in_notification_update:
					fieldname = self.set_property_after_alert
					value = self.property_value
					if doc.meta.get_field(fieldname).fieldtype in frappe.model.numeric_fieldtypes:
						value = frappe.utils.cint(value)

					doc.reload()
					doc.set(fieldname, value)
					doc.flags.updater_reference = {
						"doctype": self.doctype,
						"docname": self.name,
						"label": _("via Notification"),
					}
					doc.flags.in_notification_update = True
					doc.save(ignore_permissions=True)
					doc.flags.in_notification_update = False
			except Exception:
				frappe.log_error(
					"Document update failed",
					reference_doctype=get_reference_doctype(doc),
					reference_name=get_reference_name(doc),
				)

	def send_notification_by_channel(self, doc, context):
		"""Send notification based on the specified channel."""
		try:
			if self.channel == "Email":
				self.send_an_email(doc, context)
			elif self.channel == "Slack":
				self.send_a_slack_msg(doc, context)
			elif self.channel == "SMS":
				self.send_sms(doc, context)
			elif self.channel == "System Notification":
				self.create_system_notification(doc, context)

			# Additionally, if explicitly enabled, create a system notification
			# even when the primary channel is not "System Notification".
			if self.send_system_notification and self.channel != "System Notification":
				self.create_system_notification(doc, context)
		except Exception:
			frappe.log_error(
				title=_("Failed to send Notification: {0}").format(self.name),
				reference_doctype=get_reference_doctype(doc),
				reference_name=get_reference_name(doc),
			)

	def create_system_notification(self, doc, context):
		if self.flags.message:
			subject = self.flags.subject
			message = self.flags.message
		else:
			subject = self.subject
			if "{" in subject:
				subject = frappe.render_template(self.subject, context)

			message = frappe.render_template(self.message, context)

		attachments = self.get_attachment(doc)

		recipients, cc, bcc = self.get_list_of_recipients(doc, context)

		users = recipients + cc + bcc

		if not users:
			return

		notification_doc = {
			"type": "Alert",
			"document_type": get_reference_doctype(doc),
			"document_name": get_reference_name(doc),
			"subject": subject,
			"from_user": doc.modified_by or doc.owner,
			"email_content": message,
			"attached_file": json.dumps(attachments) if attachments else None,
		}

		notification_type = self.get_notification_type()
		if notification_type:
			set_notification_last_scheduled(
				doc.doctype,
				doc.name,
				notification_type,
				"System Notification",
				child_doctype=context.get("child_doctype"),
				child_name=context.get("child_name"),
			)

		enqueue_create_notification(
			users,
			notification_doc,
			notification_type=notification_type,
			child_doctype=context.get("child_doctype"),
			child_name=context.get("child_name"),
			enqueue_after_commit=True,
		)

	def send_an_email(self, doc, context):
		from email.utils import formataddr

		from frappe.core.doctype.communication.email import _make as make_communication

		if self.use_email_template and self.email_template:
			email_template = frappe.get_cached_doc("Email Template", self.email_template)
			subject = email_template.get_formatted_subject(context)
			message = email_template.get_formatted_response(context)
		else:
			subject = self.subject
			if "{" in subject:
				subject = frappe.render_template(self.subject, context)

			message = frappe.render_template(self.message, context)

		self.flags.subject = subject
		self.flags.message = message

		attachments = self.get_attachment(doc)
		recipients, cc, bcc = self.get_list_of_recipients(doc, context)
		if not (recipients or cc or bcc):
			return

		sender = None
		if self.sender and self.sender_email:
			sender = formataddr((self.sender, self.sender_email))

		communication = None
		# Add mail notification to communication list
		# No need to add if it is already a communication.
		if doc.doctype != "Communication":
			timeline_doctype, timeline_name = self.get_timeline_doctype_and_name(doc)

			communication = make_communication(
				doctype=get_reference_doctype(doc),
				name=get_reference_name(doc),
				content=message,
				subject=subject,
				sender=sender,
				recipients=recipients,
				communication_medium="Email",
				send_email=False,
				attachments=attachments,
				cc=cc,
				bcc=bcc,
				communication_type="Automated Message",
				timeline_doctype=timeline_doctype,
				timeline_name=timeline_name,
			).get("name")

		notification_type = self.get_notification_type()
		if notification_type:
			set_notification_last_scheduled(
				doc.doctype,
				doc.name,
				notification_type,
				"Email",
				child_doctype=context.get("child_doctype"),
				child_name=context.get("child_name"),
			)

		# We expect at most one print format attachment, but we don't know where it is.
		print_letterhead = any(
			attachment.get("print_letterhead")
			for attachment in attachments
			if attachment.get("print_format_attachment") == 1
		)

		frappe.sendmail(
			recipients=recipients,
			subject=subject,
			sender=sender,
			cc=cc,
			bcc=bcc,
			message=message,
			reference_doctype=get_reference_doctype(doc),
			reference_name=get_reference_name(doc),
			child_doctype=context.get("child_doctype"),
			child_name=context.get("child_name"),
			attachments=attachments,
			expose_recipients="header",
			print_letterhead=print_letterhead,
			communication=communication,
			notification_type=notification_type,
			with_container=self.with_container,
		)

	def send_a_slack_msg(self, doc, context):
		message = frappe.render_template(self.message, context)
		self.flags.message = message

		send_slack_message(
			webhook_url=self.slack_webhook_url,
			message=message,
			reference_doctype=get_reference_doctype(doc),
			reference_name=get_reference_name(doc),
		)

	def send_sms(self, doc, context):
		if frappe.are_sms_muted():
			return

		message = frappe.render_template(self.message, context)
		self.flags.message = message

		timeline_doctype, timeline_name = self.get_timeline_doctype_and_name(doc)
		notification_type = self.get_notification_type()

		receiver_list = self.get_receiver_list(doc, context, format_sms=True)
		if not receiver_list:
			return

		if notification_type:
			set_notification_last_scheduled(
				doc.doctype,
				doc.name,
				notification_type,
				"SMS",
				child_doctype=context.get("child_doctype"),
				child_name=context.get("child_name"),
			)

		send_sms(
			receiver_list=receiver_list,
			message=message,
			reference_doctype=get_reference_doctype(doc),
			reference_name=get_reference_name(doc),
			child_doctype=context.get("child_doctype"),
			child_name=context.get("child_name"),
			notification_type=notification_type,
			party_doctype=timeline_doctype,
			party=timeline_name,
			queue=True,
			automated=True,
		)

	def get_list_of_recipients(self, doc, context):
		recipients = []
		cc = []
		bcc = []

		eval_globals = get_safe_globals()

		for recipient in self.recipients:
			if recipient.condition:
				if not frappe.safe_eval(recipient.condition, eval_globals, context):
					continue

			recipients.extend(get_emails_from_template(recipient.recipient, context))

			if recipient.receiver_by_document_field:
				fields = recipient.receiver_by_document_field.split(",")
				# fields from child table
				if len(fields) > 1:
					for d in doc.get(fields[1]):
						email_id = d.get(fields[0])
						if validate_email_address(email_id):
							recipients.append(email_id)
				# field from parent doc
				else:
					email_ids_value = doc.get(fields[0])
					if validate_email_address(email_ids_value):
						email_ids = email_ids_value.replace(",", "\n")
						recipients = recipients + email_ids.split("\n")

			cc.extend(get_emails_from_template(recipient.cc, context))
			bcc.extend(get_emails_from_template(recipient.bcc, context))

			# For sending emails to specified role
			if recipient.receiver_by_role:
				emails = get_info_based_on_role(recipient.receiver_by_role, "email", ignore_permissions=True)

				for email in emails:
					recipients = recipients + email.split("\n")

		if self.send_to_all_assignees:
			recipients = recipients + get_assignees(doc)

		return list(set(recipients)), list(set(cc)), list(set(bcc))

	def get_receiver_list(self, doc, context, format_sms=False):
		"""return receiver list based on the doc field and role specified"""
		receiver_list = []

		eval_globals = get_safe_globals()

		for recipient in self.recipients:
			if recipient.condition:
				if not frappe.safe_eval(recipient.condition, eval_globals, context):
					continue

			receiver_list.extend(get_emails_from_template(recipient.recipient, context))

			# For sending messages to the owner's mobile phone number
			if recipient.receiver_by_document_field == "owner":
				receiver_list += get_user_info([dict(user_name=doc.get("owner"))], "mobile_no")
			# For sending messages to the number specified in the receiver field
			elif recipient.receiver_by_document_field:
				receiver_list.append(doc.get(recipient.receiver_by_document_field))

			# For sending messages to specified role
			if recipient.receiver_by_role:
				receiver_list += get_info_based_on_role(
					recipient.receiver_by_role, "mobile_no", ignore_permissions=True
				)

		receiver_list = clean_receiver_nos(receiver_list, format_sms=format_sms)

		return receiver_list

	def get_timeline_doctype_and_name(self, doc):
		if self.timeline_field:
			timeline_name = doc.get(self.timeline_field)
			df = doc.meta.get_field(self.timeline_field)
			if timeline_name and df:
				if df.fieldtype == "Link":
					return df.options, timeline_name
				elif df.fieldtype == "Dynamic Link" and doc.get(df.options):
					return doc.get(df.options), timeline_name

		return None, None

	def get_attachment(self, doc) -> list[dict]:
		"""Check Attachment Settings and return attachments accordingly"""

		hooked_attachment = doc.run_method("get_notification_attachment", self.get_notification_type())
		if hooked_attachment is not None:
			return hooked_attachment		

		attachments = []

		if self.attach_print:
			attachments.append(self.get_print(doc))

		if self.attach_files == "From Field" and self.from_attach_field:
			attachments.append({"file_url": doc.get(self.from_attach_field)})
		elif self.attach_files == "All":
			attachments.extend(
				frappe.get_all(
					"File",
					fields=["file_url"],
					filters={"attached_to_doctype": self.document_type, "attached_to_name": doc.name},
				)
			)

		return attachments

	def get_print(self, doc):
		"""check print settings and return dict with print info"""

		print_settings = frappe.get_doc("Print Settings", "Print Settings")
		if (doc.docstatus == 0 and not print_settings.allow_print_for_draft) or (
			doc.docstatus == 2 and not print_settings.allow_print_for_cancelled
		):
			# ignoring attachment as draft and cancelled documents are not allowed to print
			status = "Draft" if doc.docstatus == 0 else "Cancelled"
			frappe.throw(
				_(
					"""Not allowed to attach {0} document, please enable Allow Print For {0} in Print Settings"""
				).format(status),
				title=_("Error in Notification"),
			)
		else:
			return {
				"print_format_attachment": 1,
				"doctype": doc.doctype,
				"name": doc.name,
				"print_format": self.print_format,
				"print_letterhead": print_settings.with_letterhead,
				"lang": doc.get("language") or frappe.db.get_value("Print Format", self.print_format, "default_print_language")
				if self.print_format
				else "en",
			}

	def get_template(self, md_as_html=False):
		module = get_doc_module(self.module, self.doctype, self.name)

		path = os.path.join(os.path.dirname(module.__file__), frappe.scrub(self.name))
		extension = FORMATS.get(self.message_type, ".md")
		file_path = path + extension

		template = ""

		if os.path.exists(file_path):
			with open(file_path) as f:
				template = f.read()

		if not template:
			return

		if extension == ".md":
			return frappe.utils.md_to_html(template)

		return template

	def load_standard_properties(self, context):
		"""load templates and run get_context"""
		module = get_doc_module(self.module, self.doctype, self.name)
		if module:
			if hasattr(module, "get_context"):
				out = module.get_context(context)
				if out:
					context.update(out)

		self.message = self.get_template(md_as_html=True)

	def on_trash(self):
		frappe.cache.hdel("notifications", self.document_type)

	def get_notification_type(self):
		return self.get("notification_type") or self.name


@frappe.whitelist()
def get_documents_for_today(notification):
	notification = frappe.get_doc("Notification", notification)
	notification.check_permission("read")
	return [d.name for d in notification.get_documents_for_today()]


def trigger_daily_alerts():
	trigger_notifications(None, "daily")


def trigger_notifications(doc, method=None):
	if frappe.flags.in_import or frappe.flags.in_patch:
		# don't send notifications while syncing or patching
		return

	if method == "daily":
		doc_list = frappe.get_all(
			"Notification", filters={"event": ("in", ("Days Before", "Days After")), "enabled": 1}
		)
		for d in doc_list:
			alert = frappe.get_doc("Notification", d.name)

			for doc in alert.get_documents_for_today():
				evaluate_alert(doc, alert, alert.event)
				frappe.db.commit()


def evaluate_alert(doc: Document, alert, event, context=None):
	from jinja2 import TemplateError

	try:
		if isinstance(alert, str):
			alert = frappe.get_doc("Notification", alert)

		if not context:
			context = {}

		condition_context = context.copy()
		condition_context.update(get_context(doc))

		if alert.condition:
			if not frappe.safe_eval(alert.condition, get_safe_globals(), condition_context):
				return

		notification_type = alert.get_notification_type()
		validation = run_validate_notification(
			doc,
			notification_type,
			child_doctype=context.get("child_doctype"),
			child_name=context.get("child_name"),
			throw=False,
		)
		if not validation:
			return

		if alert.send_only_once:
			notification_count = get_notification_last_scheduled(
				doc.doctype,
				doc.name,
				notification_type,
				alert.channel,
				child_doctype=context.get("child_doctype"),
				child_name=context.get("child_name"),
			)
			if notification_count:
				return False

		if event == "Value Change" and not doc.is_new():
			if not frappe.db.has_column(doc.doctype, alert.value_changed):
				alert.db_set("enabled", 0)
				alert.log_error(f"Notification {alert.name} has been disabled due to missing field")
				return

			doc_before_save = doc.get_doc_before_save()
			field_value_before_save = doc_before_save.get(alert.value_changed) if doc_before_save else None

			fieldtype = doc.meta.get_field(alert.value_changed).fieldtype
			if cast(fieldtype, doc.get(alert.value_changed)) == cast(fieldtype, field_value_before_save):
				# value not changed
				return

		if event != "Value Change" and not doc.is_new():
			# reload the doc for the latest values & comments,
			# except for validate type event.
			doc.reload()
		alert.send(doc, context=context)
	except TemplateError:
		message = _("Error while evaluating Notification {0}. Please fix your template.").format(
			frappe.utils.get_link_to_form("Notification", alert.name)
		)
		frappe.throw(message, title=_("Error in Notification"))
	except Exception as e:
		title = str(e)
		message = frappe.get_traceback(with_context=True)
		frappe.log_error(title=title, message=message, reference_doctype=doc.doctype, reference_name=doc.name)
		msg = f"<details><summary>{title}</summary>{message}</details>"
		frappe.throw(msg, title=_("Error in Notification"))


def get_doc_for_notification_triggers(reference_doctype, reference_name):
	if not reference_doctype or not reference_name:
		return

	try:
		controller = get_controller(reference_doctype)
		has_validate_notification = hasattr(controller, "validate_notification")
		if has_validate_notification:
			doc = frappe.get_doc(reference_doctype, reference_name)
			return doc
	except ImportError:
		pass


def run_validate_notification(doc, notification_type=None, child_doctype=None, child_name=None, throw=True):
	notification_type = cstr(notification_type)
	validation = doc.run_method("validate_notification",
		notification_type=notification_type, child_doctype=child_doctype, child_name=child_name, throw=throw)

	if validation is None:
		return True
	else:
		return cint(validation)


def has_notification(reference_doctype, notification_type=None, trigger_method=None):
	if trigger_method and Document.has_method(reference_doctype, trigger_method):
		return True

	notification_type = cstr(notification_type)

	template = frappe.db.sql_list("""
		select name
		from `tabNotification`
		where document_type = %s and ifnull(notification_type, '') = %s
			and enabled = 1
		limit 1
	""", [reference_doctype, notification_type])

	return len(template) > 0


def get_context(doc):
	return {
		"doc": doc,
		"nowdate": nowdate,
	}


def get_assignees(doc):
	assignees = []
	assignees = frappe.get_all(
		"ToDo",
		filters={"status": "Open", "reference_name": doc.name, "reference_type": doc.doctype},
		fields=["allocated_to"],
	)

	return [d.allocated_to for d in assignees]


def get_emails_from_template(template, context):
	if not template:
		return ()

	emails = frappe.render_template(template, context) if "{" in template else template
	return filter(None, emails.replace(",", "\n").split("\n"))


def get_reference_doctype(doc):
	return doc.parenttype if doc.meta.istable else doc.doctype


def get_reference_name(doc):
	return doc.parent if doc.meta.istable else doc.name
