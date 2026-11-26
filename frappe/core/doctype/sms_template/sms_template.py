# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.core.doctype.sms_settings.sms_settings import get_contact_number
from frappe.model.document import Document
from frappe.utils import cstr


class SMSTemplate(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		enabled: DF.Check
		message: DF.Text
		notification_key: DF.Data | None
		reference_doctype: DF.Link

	# end: auto-generated types
	def autoname(self):
		self.name = self.reference_doctype
		if self.notification_key:
			self.name += "-" + self.notification_key

	def get_rendered_message(self, context=None, doc=None):
		context = get_context(context, doc)
		message = frappe.render_template(self.message, context)
		return message


@frappe.whitelist()
def get_sms_defaults(
	dt: str,
	dn: str,
	notification_key: str | None = None,
	contact: str | None = None,
	mobile_no: str | None = None,
	party_doctype: str | None = None,
	party: str | None = None,
):
	if not mobile_no and (contact or party_doctype or party):
		mobile_no = get_contact_number(contact, party_doctype, party)

	sms_template = get_sms_template(dt, notification_key)

	message = ""
	if sms_template:
		doc = frappe.get_doc(dt, dn)
		message = sms_template.get_rendered_message(doc=doc)

	return {
		"mobile_no": mobile_no,
		"message": message,
	}


def get_sms_template_message(notification_key=None, doc=None, context=None):
	sms_template = get_sms_template(doc.doctype, notification_key)
	if not sms_template:
		return ""

	context = get_context(context, doc)
	return sms_template.get_rendered_message(context=context)


def get_sms_template(reference_doctype, notification_key=None):
	notification_key = cstr(notification_key)

	template = frappe.db.sql_list(
		"""
		select name
		from `tabSMS Template`
		where reference_doctype = %s and ifnull(notification_key, '') = %s and enabled = 1
		limit 1
	""",
		[reference_doctype, notification_key],
	)

	if template:
		template_doc = frappe.get_cached_doc("SMS Template", template[0])
		return template_doc
	else:
		return None


def get_context(context=None, doc=None):
	if not context:
		context = {"doc": {}}

	if doc:
		context["doc"] = doc

	return context
