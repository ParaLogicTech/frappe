# Copyright (c) 2022, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import cint, cstr, get_datetime, now_datetime

exclude_from_linked_with = True


class NotificationCount(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		child_doctype: DF.Link | None
		child_name: DF.Data | None
		last_scheduled_dt: DF.Datetime | None
		last_sent_dt: DF.Datetime | None
		notification_count: DF.Int
		notification_medium: DF.Data | None
		notification_type: DF.Data
		reference_doctype: DF.Link
		reference_name: DF.DynamicLink | None
	# end: auto-generated types
	pass


def add_notification_count(
	reference_doctype,
	reference_name,
	notification_type,
	notification_medium,
	child_doctype=None,
	child_name=None,
	count=1,
):
	count = cint(count) or 1

	doc = get_notification_count_doc(
		reference_doctype,
		reference_name,
		notification_type,
		notification_medium,
		child_doctype=child_doctype,
		child_name=child_name,
		for_update=True,
	)
	doc.notification_count = cint(doc.notification_count) + count
	doc.last_sent_dt = now_datetime()
	doc.save(ignore_permissions=True)


def get_notification_count(
	reference_doctype,
	reference_name,
	notification_type,
	notification_medium,
	child_doctype=None,
	child_name=None,
):
	doc = get_notification_count_doc(
		reference_doctype,
		reference_name,
		notification_type,
		notification_medium,
		child_doctype=child_doctype,
		child_name=child_name,
	)
	return cint(doc.get("notification_count"))


def set_notification_last_scheduled(
	reference_doctype,
	reference_name,
	notification_type,
	notification_medium,
	child_doctype=None,
	child_name=None,
	now_dt=None,
):
	doc = get_notification_count_doc(
		reference_doctype,
		reference_name,
		notification_type,
		notification_medium,
		child_doctype=child_doctype,
		child_name=child_name,
		for_update=True,
	)
	doc.last_scheduled_dt = get_datetime(now_dt)
	doc.save(ignore_permissions=True)


def get_notification_last_scheduled(
	reference_doctype,
	reference_name,
	notification_type,
	notification_medium,
	child_doctype=None,
	child_name=None,
):
	doc = get_notification_count_doc(
		reference_doctype,
		reference_name,
		notification_type,
		notification_medium,
		child_doctype=child_doctype,
		child_name=child_name,
	)
	return get_datetime(doc.get("last_scheduled_dt")) if doc.get("last_scheduled_dt") else None


def clear_notification_count(reference_doctype, reference_name, child_doctype=None, child_name=None):
	reference_name = cstr(reference_name)

	delete_query = "delete from `tabNotification Count` where reference_doctype = %s and reference_name = %s"
	arg_list = [reference_doctype, reference_name]

	if child_doctype and child_name:
		delete_query += " and child_doctype = %s and child_name=%s"
		arg_list += [child_doctype, child_name]

	frappe.db.sql(delete_query, arg_list)


def get_all_notification_count(reference_doctype, reference_name, child_doctype=None, child_name=None):
	if not reference_doctype:
		return []

	reference_name = cstr(reference_name)

	filters = {"reference_doctype": reference_doctype, "reference_name": reference_name}
	fields = ["notification_type", "notification_medium", "notification_count"]

	if child_doctype and child_name:
		filters.update(
			{
				"child_doctype": child_doctype,
				"child_name": child_name,
			}
		)

	return frappe.get_all("Notification Count", filters=filters, fields=fields, order_by="creation")


def get_notification_count_doc(
	reference_doctype,
	reference_name,
	notification_type,
	notification_medium,
	child_doctype=None,
	child_name=None,
	for_update=False,
):
	reference_name = cstr(reference_name)
	notification_medium = cstr(notification_medium)

	filters = {
		"reference_doctype": reference_doctype,
		"reference_name": reference_name,
		"notification_type": notification_type,
		"notification_medium": notification_medium,
	}

	if child_doctype and child_name:
		filters.update({"child_doctype": child_doctype, "child_name": child_name})

	name = frappe.db.get_value("Notification Count", filters)

	if name:
		doc = frappe.get_doc("Notification Count", name, for_update=for_update)
	else:
		doc = frappe.get_doc({"doctype": "Notification Count", **filters})

	return doc
