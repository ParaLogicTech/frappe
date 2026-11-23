frappe.provide("frappe.ui.form");

frappe.ui.form.AddressQuickEntryForm = class AddressQuickEntryForm extends (
	frappe.ui.form.QuickEntryForm
) {
	render_dialog() {
		super.render_dialog();
		const last_doc = frappe.contacts.get_last_doc(this.doc);
		if (
			frappe.dynamic_link &&
			frappe.dynamic_link.doc &&
			frappe.dynamic_link.doc.name == last_doc.docname
		) {
			this.doc.links = [
				{
					idx: 1,
					link_doctype: frappe.dynamic_link.doctype,
					link_name: frappe.dynamic_link.doc[frappe.dynamic_link.fieldname],
				},
			];
		}
	}
};
