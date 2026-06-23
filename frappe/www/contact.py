# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

from contextlib import suppress

import frappe
from frappe import _, unscrub
from frappe.rate_limiter import rate_limit
from frappe.utils import escape_html, validate_email_address, cint
import json

sitemap = 1


def get_context(context):
	doc = frappe.get_doc("Contact Us Settings", "Contact Us Settings")
	if doc.is_disabled:
		frappe.local.flags.redirect_location = "/404"
		raise frappe.Redirect

	out = {"parents": [{"name": _("Home"), "route": "/"}]}
	context.update(out)

	return out


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=100, seconds=60 * 60)
def send_message(sender, message, subject="Website Query", args=None, create_communication=1):
	doc = frappe.get_doc("Contact Us Settings", "Contact Us Settings")
	if doc.is_disabled:
		return

	if not sender:
		frappe.throw(_("Please enter your email address"))

	sender = validate_email_address(sender, throw=True)

	message = escape_html(message)

	if not args:
		args = {}
	if isinstance(args, str):
		args = json.loads(args)

	context = {
		"sender": sender,
		"subject": subject,
	}
	for key, value in args.items():
		if not context.get(key):
			context[key] = value

	context["message"] = message

	with suppress(frappe.OutgoingEmailError):
		# Internal / Forward Email
		if forward_to_email := frappe.db.get_single_value("Contact Us Settings", "forward_to_email"):
			forward_email_content = []
			for key, value in context.items():
				if not value:
					continue

				label = unscrub(key)

				if isinstance(value, str):
					value = frappe.format(value, df={"fieldtype": "Text"})
				else:
					value = frappe.format(value)

				forward_email_content.append(f"<b>{label}:</b> {value}")

			forward_email_content = "<br>".join(forward_email_content)

			frappe.sendmail(recipients=forward_to_email, reply_to=sender, content=forward_email_content, subject=subject)

		# Acknowledgement / Confirmation Email
		subject = "We've received your query!"
		content = f"<div style='white-space: pre-wrap'>Thank you for reaching out to us. We will get back to you at the earliest.\n\n\nYour query:\n\n{message}</div>"

		if email_template := frappe.db.get_single_value("Contact Us Settings", "confirmation_email_template"):
			email_template_doc = frappe.get_cached_doc("Email Template", email_template)
			formatted_template = email_template_doc.get_formatted_email(context)

			subject = formatted_template['subject']
			content = formatted_template['message']

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
