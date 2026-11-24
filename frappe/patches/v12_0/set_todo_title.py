import frappe


def execute():
	frappe.reload_doctype("ToDo")

	todos = frappe.get_all("ToDo", filters={"title": ["is", "not set"]})
	for d in todos:
		doc = frappe.get_doc("ToDo", d.name)
		doc.set_title()
		doc.db_set("title", doc.title)
