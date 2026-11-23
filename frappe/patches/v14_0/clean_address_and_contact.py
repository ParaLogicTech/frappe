import frappe


def execute():
	frappe.reload_doctype("Address")
	frappe.reload_doctype("Contact")

	addresses = frappe.get_all("Address", pluck="name")
	contacts = frappe.get_all("Contact", pluck="name")

	print("Cleaning Contact Names")
	for name in contacts:
		doc = frappe.get_doc("Contact", name)
		doc.clean_contact_name()
		doc.db_update()
		doc.clear_cache()

	print("Cleaning Addresses")
	for name in addresses:
		doc = frappe.get_doc("Address", name)
		doc.clean_address()
		doc.db_update()
		doc.clear_cache()
