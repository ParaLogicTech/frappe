// Copyright (c) 2016, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Contact", {
	onload(frm) {
		frm.email_field = "email_id";
	},
	refresh: function (frm) {
		if (frm.doc.__islocal) {
			const last_doc = frappe.contacts.get_last_doc(frm);
			if (
				frappe.dynamic_link &&
				frappe.dynamic_link.doc &&
				frappe.dynamic_link.doc.name == last_doc.docname
			) {
				frm.set_value("links", "");
				frm.add_child("links", {
					link_doctype: frappe.dynamic_link.doctype,
					link_name: frappe.dynamic_link.doc[frappe.dynamic_link.fieldname],
				});
			}
		}

		if (!frm.doc.user && !frm.is_new() && frm.perm[0].write) {
			frm.add_custom_button(__("Invite as User"), function () {
				return frappe.call({
					method: "frappe.contacts.doctype.contact.contact.invite_user",
					args: {
						contact: frm.doc.name,
					},
					callback: function (r) {
						frm.set_value("user", r.message);
					},
				});
			});
		}
		frm.set_query("link_doctype", "links", function () {
			return {
				query: "frappe.contacts.address_and_contact.filter_dynamic_link_doctypes",
				filters: {
					fieldtype: "HTML",
					fieldname: "contact_html",
				},
			};
		});
		frm.refresh_field("links");

		let numbers = frm.doc.phone_nos;
		if (numbers && numbers.length && frappe.phone_call.handler) {
			frm.add_custom_button(__("Call"), () => {
				numbers = frm.doc.phone_nos
					.sort((prev, next) => next.is_primary_mobile_no - prev.is_primary_mobile_no)
					.map((d) => d.phone);
				frappe.phone_call.handler(numbers);
			});
		}

		if (frm.doc.links) {
			frappe.call({
				method: "frappe.contacts.doctype.contact.contact.address_query",
				args: { links: frm.doc.links },
				callback: function (r) {
					if (r && r.message) {
						frm.set_query("address", function () {
							return {
								filters: {
									name: ["in", r.message],
								},
							};
						});
					}
				},
			});

			for (let i in frm.doc.links) {
				let link = frm.doc.links[i];
				frm.add_custom_button(
					__("{0}: {1}", [__(link.link_doctype), __(link.link_name)]),
					function () {
						frappe.set_route("Form", link.link_doctype, link.link_name);
					},
					__("Links")
				);
			}
		}
	},
	validate: function (frm) {
		// clear linked customer / supplier / sales partner on saving...
		if (frm.doc.links) {
			frm.doc.links.forEach(function (d) {
				frappe.model.remove_from_locals(d.link_doctype, d.link_name);
			});
		}
	},
	after_save: function (frm) {
		frappe.run_serially([
			() => frappe.timeout(1),
			() => {
				const last_doc = frappe.contacts.get_last_doc(frm);
				if (
					frappe.dynamic_link &&
					frappe.dynamic_link.doc &&
					frappe.dynamic_link.doc.name == last_doc.docname
				) {
					for (let i in frm.doc.links) {
						let link = frm.doc.links[i];
						if (
							last_doc.doctype == link.link_doctype &&
							last_doc.docname == link.link_name
						) {
							frappe.set_route("Form", last_doc.doctype, last_doc.docname);
						}
					}
				}
			},
		]);
	},
	sync_with_google_contacts: function (frm) {
		if (frm.doc.sync_with_google_contacts) {
			frappe.db.get_value(
				"Google Contacts",
				{ email_id: frappe.session.user },
				"name",
				(r) => {
					if (r && r.name) {
						frm.set_value("google_contacts", r.name);
					}
				}
			);
		}
	},
});

frappe.ui.form.on("Dynamic Link", {
	link_name: function (frm, cdt, cdn) {
		var child = locals[cdt][cdn];
		if (child.link_name) {
			frappe.model.with_doctype(child.link_doctype, function () {
				var title_field = frappe.get_meta(child.link_doctype).title_field || "name";
				frappe.model.get_value(
					child.link_doctype,
					child.link_name,
					title_field,
					function (r) {
						frappe.model.set_value(cdt, cdn, "link_title", r[title_field]);
					}
				);
			});
		}
	},
});

frappe.ui.form.on("Contact", {
	validate: function (frm) {
		frm.events.format_mobile_nos(frm);
		frappe.regional.pakistan.format_cnic(frm, "tax_cnic");
		frappe.regional.pakistan.format_mobile_no(frm, "mobile_no");
		frappe.regional.pakistan.format_mobile_no(frm, "mobile_no_2");
	},

	tax_cnic: function (frm) {
		frappe.regional.pakistan.format_cnic(frm, "tax_cnic");
	},

	mobile_no: function (frm) {
		frappe.regional.pakistan.format_mobile_no(frm, "mobile_no");
	},
	mobile_no_2: function (frm) {
		frappe.regional.pakistan.format_mobile_no(frm, "mobile_no_2");
	},

	format_mobile_nos: function (frm) {
		if (frappe.sys_defaults.country != "Pakistan") {
			return;
		}

		$.each(frm.doc.phone_nos || [], function (i, d) {
			if (d.is_primary_mobile_no) {
				d.phone = frappe.regional.pakistan.get_formatted_mobile_no(d.phone);
				refresh_field('phone', d.name, 'phone_nos');
			}
		});
	},
});

frappe.ui.form.on("Contact Phone", {
	phone: function(frm) {
		frm.events.format_mobile_nos(frm);
	},
	is_primary_mobile_no: function(frm) {
		frm.events.format_mobile_nos(frm);
	}
});
