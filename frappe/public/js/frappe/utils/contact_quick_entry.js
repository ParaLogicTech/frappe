frappe.provide("frappe.ui.form");

frappe.ui.form.ContactQuickEntryForm = class ContactQuickEntryForm extends (
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

		if (this.dialog.fields_dict["tax_cnic"]) {
			this.dialog.fields_dict["tax_cnic"].df.onchange = () => {
				var value = this.dialog.get_value("tax_cnic");
				value = frappe.regional.get_formatted_cnic(value);
				this.dialog.doc.tax_cnic = value;
				this.dialog.get_field("tax_cnic").refresh();
			};
		}

		if (this.dialog.fields_dict["mobile_no"]) {
			this.dialog.fields_dict["mobile_no"].df.onchange = () => {
				var value = this.dialog.get_value("mobile_no");
				value = frappe.regional.get_formatted_mobile_no(value);
				this.dialog.doc.mobile_no = value;
				this.dialog.get_field("mobile_no").refresh();
			};
		}

		if (this.dialog.fields_dict["mobile_no_2"]) {
			this.dialog.fields_dict["mobile_no_2"].df.onchange = () => {
				var value = this.dialog.get_value("mobile_no_2");
				value = frappe.regional.get_formatted_mobile_no(value);
				this.dialog.doc.mobile_no_2 = value;
				this.dialog.get_field("mobile_no_2").refresh();
			};
		}
	}
};
