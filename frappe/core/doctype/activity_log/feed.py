# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
import frappe.permissions
from frappe import _
from frappe.core.doctype.activity_log.activity_log import add_authentication_log
from frappe.utils import cstr, get_fullname


def update_feed(doc, method=None):
	if frappe.flags.in_patch or frappe.flags.in_install or frappe.flags.in_import:
		return

	if doc._action != "save" or doc.flags.ignore_feed:
		return

	if doc.doctype == "Activity Log" or doc.meta.issingle:
		return

	if hasattr(doc, "get_feed"):
		feed = doc.get_feed()

		if feed:
			if isinstance(feed, str):
				feed = {"subject": feed}

			feed = frappe._dict(feed)
			doctype = feed.doctype or doc.doctype
			name = feed.name or doc.name

			# delete earlier feed
			frappe.db.sql(
				"""
				delete from `tabActivity Log`
				where reference_doctype=%s and reference_name=%s and date(creation) = %s
					and ifnull(link_doctype, '') = %s
			""",
				(doctype, name, frappe.utils.today(), cstr(feed.link_doctype)),
			)

			log = frappe.get_doc(
				{
					"doctype": "Activity Log",
					"reference_doctype": doctype,
					"reference_name": name,
					"subject": feed.subject,
					"full_name": get_fullname(doc.owner),
					"reference_owner": frappe.db.get_value(doctype, name, "owner"),
					"link_doctype": feed.link_doctype,
					"link_name": feed.link_name,
					"timeline_doctype": feed.timeline_doctype,
					"timeline_name": feed.timeline_name,
				}
			)

			log.parent_doc = doc
			log.insert(ignore_permissions=True)


def login_feed(login_manager):
	if login_manager.user != "Guest":
		subject = _("{0} logged in").format(get_fullname(login_manager.user))
		add_authentication_log(subject, login_manager.user)


def logout_feed(user, reason):
	if user and user != "Guest":
		subject = _("{0} logged out: {1}").format(get_fullname(user), frappe.bold(reason))
		add_authentication_log(subject, user, operation="Logout")
