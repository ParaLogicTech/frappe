import frappe


def execute():
	frappe.db.sql("""
		delete from `tabVersion`
		where ref_doctype in ('Route History', 'Comment', 'Activity Log', 'Property Setter')
	""")
