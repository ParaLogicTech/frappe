frappe.provide("frappe.contacts");

$.extend(frappe.contacts, {
	clear_address_and_contact: function (frm) {
		for (const field of ["address_html", "contact_html"]) {
			$(frm.fields_dict[field]?.wrapper)?.html("");
		}
	},

	render_address_and_contact: function (frm) {
		const items = [
			{
				field: "address_html",
				data: "addr_list",
				template: "address_list",
				btn: ".btn-address",
				doctype: "Address",
			},
			{
				field: "contact_html",
				data: "contact_list",
				template: "contact_list",
				btn: ".btn-contact",
				doctype: "Contact",
			},
		];

		for (const item of items) {
			// render address or contact
			const field_wrapper = frm.fields_dict[item.field]?.wrapper;

			if (field_wrapper && frm.doc.__onload && item.data in frm.doc.__onload) {
				$(field_wrapper)
					.html(frappe.render_template(item.template, frm.doc.__onload))
					.find(item.btn)
					.on("click", () => new_record(item.doctype, frm.doc));
			}
		}
	},

	get_last_doc: function (frm) {
		const reverse_routes = frappe.route_history.slice().reverse();
		const last_route = reverse_routes.find((route) => {
			return route[0] === "Form" && route[1] !== frm.doctype;
		});
		let doctype = last_route && last_route[1];
		let docname = last_route && last_route[2];

		if (last_route && last_route.length > 3) docname = last_route.slice(2).join("/");

		return {
			doctype,
			docname,
		};
	},

	get_address_display: function (frm, address_field, display_field) {
		if (frm.updating_party_details) {
			return;
		}

		let _address_field = address_field || "address";
		let _display_field = display_field || "address_display";

		if (!frm.doc[_address_field]) {
			frm.set_value(_display_field, "");
			return;
		}

		frappe
			.xcall("frappe.contacts.doctype.address.address.get_address_display", {
				address_dict: frm.doc[_address_field],
			})
			.then((address_display) => frm.set_value(_display_field, address_display));
	},
	get_all_contact_nos: function (frm, link_doctype, link_name) {
		if (link_doctype && link_name) {
			return frappe.call({
				method: "frappe.contacts.doctype.contact.contact.get_all_contact_nos",
				args: {
					link_doctype: link_doctype,
					link_name: link_name,
				},
				callback: function (r) {
					frappe.contacts.set_all_contact_nos(frm, r.message);
				},
			})
		}
	},

	set_all_contact_nos: function (frm, contact_nos) {
		if (contact_nos) {
			if (!frm.doc.__onload) {
				frm.doc.__onload = {};
			}
			frm.doc.__onload.contact_nos = contact_nos;
		}
	},

	set_contact_no_select_options: function (frm, fieldname, number_type, allow_add) {
		var all_contact_nos = [];
		if (frm.doc.__onload && frm.doc.__onload.contact_nos) {
			all_contact_nos = frm.doc.__onload.contact_nos;
		}

		var filtered_contact_nos = number_type ? all_contact_nos.filter(d => d[number_type]) : all_contact_nos;

		var contact_nos = [];
		$.each(filtered_contact_nos, function (i, d) {
			if (!contact_nos.includes(d.phone)) {
				contact_nos.push(d.phone);
			}
		});

		var already_set = frm.doc[fieldname];
		if (already_set && !contact_nos.includes(already_set)) {
			 contact_nos.push(already_set);
		}

		var options = [''].concat(contact_nos);
		if (allow_add) {
			options.push(__('[Add New Number]'));
		}

		frm.set_df_property(fieldname, 'options', options);
	},

	add_new_number_dialog: function(frm, number_field, contact_field, contact_name_field, number_type, callback) {
		var html = `
<div class="text-center">
<button type="button" class="btn btn-primary btn-new-contact">${__("Create a New Contact")}</button>
<br/><br/>
<button type="button" class="btn btn-primary btn-existing-contact">${__("Add Number To Existing Contact")}</button>
</div>
`;

		var dialog = new frappe.ui.Dialog({
			title: __("Add New Contact Number"),
			fields: [
				{fieldtype: "HTML", options: html}
			],
		});

		dialog.show();

		$('.btn-new-contact', dialog.$wrapper).click(function () {
			dialog.hide();
			frappe.contacts.create_new_contact(frm, number_field, contact_field);
		});

		$('.btn-existing-contact', dialog.$wrapper).click(function () {
			dialog.hide();
			frappe.contacts.add_number_to_existing_contact_dialog(frm, number_field, contact_field, contact_name_field,
				number_type, callback);
		});
	},

	create_new_contact: function (frm, number_field, contact_field) {
		var field = frm.get_field(contact_field);
		if (field) {
			field.new_doc();
		}
	},

	add_number_to_existing_contact_dialog: function (frm, number_field, contact_field, contact_name_field, number_type, callback) {
		var dialog = new frappe.ui.Dialog({
			title: __("Add Number to Existing Contact"),
			fields: [
				{
					label: __("Contact"),
					fieldname: "contact",
					fieldtype: "Link",
					options: "Contact",
					reqd: 1,
					default: frm.doc[contact_field],
					get_query: () => erpnext.queries.contact_query(frm.doc),
					onchange: () => {
						var contact = dialog.get_value('contact');
						if (contact) {
							frappe.call({
								method: "frappe.contacts.doctype.contact.contact.get_contact_details",
								args: {contact: contact},
								callback: function (r) {
									if (r.message) {
										dialog.set_value('contact_display', r.message.contact_display);
									}
								}
							});
						} else {
							dialog.set_value('contact_display', "");
						}
					}
				},
				{
					label: __("Contact Name"),
					fieldname: "contact_display",
					fieldtype: "Data",
					read_only: 1,
					default: frm.doc[contact_name_field]
				},
				{
					fieldtype: "Data",
					label: __("New Number"),
					fieldname: "phone",
					reqd: 1,
					onchange: () => {
						if (number_type == "is_primary_mobile_no") {
							var value = dialog.get_value('phone');
							value = frappe.regional.get_formatted_mobile_no(value);
							dialog.fields_dict.phone.value = value;
							dialog.fields_dict.phone.refresh();
						}
					},
				},
			]
		});

		dialog.set_primary_action(__("Add"), function () {
			var values = dialog.get_values();
			if (number_type == "is_primary_mobile_no") {
				values.phone = frappe.regional.get_formatted_mobile_no(values.phone);
			}
			return frappe.call({
				method: "frappe.contacts.doctype.contact.contact.add_phone_no_to_contact",
				args: {
					"contact": values.contact,
					"phone": values.phone,
					"is_primary_mobile_no": cint(number_type == 'is_primary_mobile_no'),
					"is_primary_phone": cint(number_type == 'is_primary_phone'),
				},
				callback: function (r) {
					if (!r.exc) {
						dialog.hide();
						callback && callback(values.phone);
					}
				}
			});
		});

		dialog.show();
	},

	get_contacts_from_number: function (frm, phone_no) {
		contacts = [];
		if (phone_no && frm.doc.__onload && frm.doc.__onload.contact_nos) {
			var contacts = frm.doc.__onload.contact_nos.filter(d => d.phone == phone_no);
			contacts = contacts.map(d => d.contact);
		}
		return contacts;
	},

	address_query: function(doc) {
		if (frappe.dynamic_link) {
			if(!doc[frappe.dynamic_link.fieldname]) {
				frappe.throw(__("Please set {0}",
					[__(frappe.meta.get_label(doc.doctype, frappe.dynamic_link.fieldname, doc.name))]));
			}

			return {
				query: 'frappe.contacts.doctype.address.address.address_query',
				filters: {
					link_doctype: frappe.dynamic_link.doctype,
					link_name: doc[frappe.dynamic_link.fieldname]
				}
			};
		}
	},

	contact_query: function(doc) {
		if (frappe.dynamic_link) {
			if(!doc[frappe.dynamic_link.fieldname]) {
				frappe.throw(__("Please set {0}",
					[__(frappe.meta.get_label(doc.doctype, frappe.dynamic_link.fieldname, doc.name))]));
			}

			return {
				query: 'frappe.contacts.doctype.contact.contact.contact_query',
				filters: {
					link_doctype: frappe.dynamic_link.doctype,
					link_name: doc[frappe.dynamic_link.fieldname]
				}
			};
		}
	},
});

function new_record(doctype, source_doc) {
	frappe.dynamic_link = {
		doctype: source_doc.doctype,
		doc: source_doc,
		fieldname: "name",
	};

	return frappe.new_doc(doctype);
}
