import frappe


@frappe.whitelist()
def get_print_settings_to_show(doctype: str, docname: str):
	doc = frappe.get_doc(doctype, docname)
	doc.check_permission("read")
	print_settings = frappe.get_single("Print Settings")

	fields = doc.run_method("get_print_settings") or []

	print_settings_fields = []
	for fieldname in fields:
		df = doc.meta.get_field(fieldname)
		if df:
			df.default = doc.get(fieldname)

		if not df:
			df = print_settings.meta.get_field(fieldname)
			df.default = print_settings.get(fieldname)

		if not df:
			continue

		print_settings_fields.append(df)

	return print_settings_fields
