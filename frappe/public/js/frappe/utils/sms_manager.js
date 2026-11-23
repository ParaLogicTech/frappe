// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

frappe.SMSManager = function SMSManager(doc, options) {
	var me = this;

	if (!doc) {
		doc = {};
	}
	if (!options) {
		options = {};
	}

	this.show = function () {
		me.doctype = doc.doctype;
		me.name = doc.name;

		if (options.reference_doctype && options.reference_name) {
			me.reference_doctype = options.reference_doctype;
			me.reference_name = options.reference_name;
		} else if (doc) {
			me.reference_doctype = me.doctype;
			me.reference_name = me.name;
		}

		me.message = options.message;
		me.notification_type = options.notification_type;
		me.contact = options.contact;
		me.mobile_no = options.mobile_no;
		me.party_doctype = options.party_doctype;
		me.party = options.party;

		this.get_sms_defaults();
	};

	this.get_sms_defaults = function () {
		frappe.call({
			method: "frappe.core.doctype.sms_template.sms_template.get_sms_defaults",
			args: {
				dt: me.doctype,
				dn: me.name,
				notification_type: me.notification_type,
				contact: me.contact,
				mobile_no: me.mobile_no,
				party_doctype: me.party_doctype,
				party: me.party,
			},
			callback: function (r) {
				if (!r.exc) {
					me.mobile_no = r.message.mobile_no || me.mobile_no;
					me.message = r.message.message || me.message;
					me.show_dialog();
				}
			},
		});
	};

	this.show_dialog = function () {
		if (!me.dialog) {
			me.make_dialog();
		}

		me.dialog.set_values({
			message: me.message,
			mobile_no: me.mobile_no,
		});
		me.dialog.show();
	};

	this.make_dialog = function () {
		var d = new frappe.ui.Dialog({
			title: __("Send {0} SMS", [me.notification_type || ""]),
			width: 400,
			fields: [
				{ label: __("Mobile Number"), fieldname: "mobile_no", fieldtype: "Data", reqd: 1 },
				{ label: __("Message"), fieldname: "message", fieldtype: "Text", reqd: 1 },
				{ label: __("Send"), fieldname: "send", fieldtype: "Button" },
			],
		});

		d.fields_dict.send.input.onclick = function () {
			var btn = d.fields_dict.send.input;
			var v = me.dialog.get_values();
			if (v) {
				$(btn).set_working();
				frappe.call({
					method:
						options.method || "frappe.core.doctype.sms_settings.sms_settings.send_sms",
					args: {
						receiver_list: [v.mobile_no],
						message: v.message,
						notification_type: me.notification_type,
						reference_doctype: me.reference_doctype,
						reference_name: me.reference_name,
						party_doctype: me.party_doctype,
						party: me.party,
					},
					callback: function (r) {
						if (!r.exc) {
							me.dialog.hide();
						}
					},
					always: function () {
						$(btn).done_working();
					},
				});
			}
		};

		$(d.fields_dict.send.input).addClass("btn-primary");

		me.dialog = d;
	};

	this.show();
};

frappe.get_notification_count_str = function (frm, notification_type) {
	let counts = (frm.doc.__onload?.notification_count || [])
		.filter((d) => {
			return d.notification_type == notification_type && cint(d.notification_count);
		})
		.map((d) => `${cint(d.notification_count)} ${d.notification_medium}`);

	let counts_str = "Not Sent";
	if (counts.length) {
		counts_str = counts.join(", ");
	}
	return counts_str;
};

frappe.get_notification_count = function (frm, notification_type, notification_medium) {
	let rows = (frm.doc.__onload?.notification_count || []).filter((d) => {
		return (
			d.notification_type == notification_type &&
			(!notification_medium || d.notification_medium == notification_medium)
		);
	});

	if (rows.length) {
		return frappe.utils.sum(rows.map((d) => cint(d.notification_count)));
	} else {
		return 0;
	}
};
