// Copyright (c) 2022, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("SMS Queue", {
	refresh: function (frm) {
		if (frm.doc.reference_doctype && frm.doc.reference_name) {
			frm.add_custom_button(__(frm.doc.reference_name), () => {
				frappe.set_route("Form", frm.doc.reference_doctype, frm.doc.reference_name);
			});
		}
	},
});
