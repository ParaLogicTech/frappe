# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import json
from contextlib import suppress

import frappe
from frappe import _, unscrub
from frappe.rate_limiter import rate_limit
from frappe.utils import cint, cstr, escape_html, validate_email_address

sitemap = 1


def get_context(context):
	doc = frappe.get_doc("Contact Us Settings", "Contact Us Settings")
	if doc.is_disabled:
		frappe.local.flags.redirect_location = "/404"
		raise frappe.Redirect

	out = {"parents": [{"name": _("Home"), "route": "/"}]}
	context.update(out)

	return out


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=100, seconds=60 * 60)
def send_message(
	sender: str,
	message: str,
	subject: str = "Website Query",
	args: str | dict | None = None,
):
	process_contact_message(sender, message, subject=subject, args=args)


def process_contact_message(
	sender: str,
	message: str,
	subject: str = "Website Query",
	args: str | dict | None = None,
	create_communication: bool = True,
):
	doc = frappe.get_doc("Contact Us Settings", "Contact Us Settings")
	if doc.is_disabled:
		return

	if not sender:
		frappe.throw(_("Please enter your email address"))

	sender = validate_email_address(sender, throw=True)

	if args and isinstance(args, str):
		args = json.loads(args)

	context = get_contact_message_context(sender, subject, message, args)
	message = context["message"]

	with suppress(frappe.OutgoingEmailError):
		# Internal / Forward Email
		if forward_to_email := frappe.db.get_single_value("Contact Us Settings", "forward_to_email"):
			frappe.sendmail(
				recipients=forward_to_email,
				reply_to=sender,
				content=get_contact_message_html(context),
				subject=subject,
			)

		# Acknowledgement / Confirmation Email
		if frappe.db.get_single_value("Contact Us Settings", "send_acknowledgement_email"):
			# the default reply doesn't quote the query, so a guest can't make the site send arbitrary text
			subject = _("We've received your query!")
			reply = _("Thank you for reaching out to us. We will get back to you at the earliest.")
			content = f"<div style='white-space: pre-wrap'>{reply}</div>"

			if email_template := frappe.db.get_single_value(
				"Contact Us Settings", "confirmation_email_template"
			):
				email_template_doc = frappe.get_cached_doc("Email Template", email_template)
				formatted_template = email_template_doc.get_formatted_email(context)

				subject = formatted_template["subject"]
				content = formatted_template["message"]

			frappe.sendmail(
				recipients=sender,
				subject=subject,
				content=content,
			)

	# for clearing outgoing email error message
	frappe.clear_last_message()

	system_language = frappe.db.get_single_value("System Settings", "language")
	# add to to-do ?
	if cint(create_communication):
		frappe.get_doc(
			dict(
				doctype="Communication",
				sender=sender,
				subject=_("New Message from Website Contact Page", system_language),
				sent_or_received="Received",
				content=message,
				status="Open",
			)
		).insert(ignore_permissions=True)


def get_contact_message_context(sender: str, subject: str, message: str, args: dict | None = None) -> dict:
	# args, subject and message come from guests and are rendered into HTML emails, so escape them
	context = {
		"sender": sender,
		"subject": escape_html(subject),
	}
	for key, value in (args or {}).items():
		if not context.get(key):
			context[key] = escape_html(value)

	context["message"] = escape_html(message)
	return context


def get_contact_message_html(context: dict) -> str:
	# One "Label: value" line per value; expects the escaped context from get_contact_message_context
	lines = []
	for key, value in context.items():
		if not value:
			continue

		label = escape_html(unscrub(key))

		if isinstance(value, str):
			value = frappe.format(value, df={"fieldtype": "Text"})
		else:
			value = escape_html(cstr(frappe.format(value)))

		lines.append(f"<b>{label}:</b> {value}")

	return "<br>".join(lines)
