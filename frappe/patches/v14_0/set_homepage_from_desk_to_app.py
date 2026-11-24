import frappe


def execute():
	home_page = frappe.db.get_single_value("Website Settings", "home_page")
	if home_page == "desk":
		frappe.db.set_single_value("Website Settings", "home_page", "app", update_modified=False)
