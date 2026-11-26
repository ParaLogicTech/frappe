import frappe
from frappe.model.utils.rename_field import (
	update_property_setters,
	update_reports,
	update_user_settings,
	update_users_report_view_settings,
)
from frappe.query_builder.functions import Coalesce

DOCTYPES = ("Notification", "Notification Count", "Email Queue", "SMS Queue", "SMS Template")


def execute():
	for doctype in DOCTYPES:
		rename_notification_type_column(doctype)


def rename_notification_type_column(doctype):
	# Runs before model sync and renames the column in place, so vanilla frappe's own notification_type field on
	# Notification gets a new, empty column instead of taking over this one with the old values.
	frappe.cache.hdel("table_columns", f"tab{doctype}")
	# on older sites the table may not exist yet: model sync creates it with the new column
	if not frappe.db.table_exists(doctype, cached=False):
		return

	if not frappe.db.has_column(doctype, "notification_type"):
		return

	if frappe.db.has_column(doctype, "notification_key"):
		table = frappe.qb.DocType(doctype)
		(
			frappe.qb.update(table)
			.set(table.notification_key, table.notification_type)
			.where(Coalesce(table.notification_key, "") == "")
		).run()
		frappe.db.sql_ddl(f"alter table `tab{doctype}` drop column `notification_type`")
	else:
		frappe.db.rename_column(doctype, "notification_type", "notification_key")

	frappe.cache.hdel("table_columns", f"tab{doctype}")

	update_reports(doctype, "notification_type", "notification_key")
	update_users_report_view_settings(doctype, "notification_type", "notification_key")
	update_property_setters(doctype, "notification_type", "notification_key")
	update_user_settings(doctype, "notification_type", "notification_key")
