import frappe
from frappe.model.utils.rename_field import rename_field

DOCTYPES = ("Notification", "Notification Count", "Email Queue", "SMS Queue", "SMS Template")


def execute():
	for doctype in DOCTYPES:
		rename_notification_type_field(doctype)


def rename_notification_type_field(doctype):
	if not frappe.db.has_column(doctype, "notification_type"):
		return

	rename_field(doctype, "notification_type", "notification_key")

	# rename_field copies the values and keeps the old column. Drop it, as vanilla frappe adds its own
	# notification_type field to Notification, which must not pick up the old values.
	frappe.db.sql_ddl(f"alter table `tab{doctype}` drop column `notification_type`")
	frappe.cache.hdel("table_columns", f"tab{doctype}")
