frappe.provide("frappe.regional.pakistan");

Object.assign(frappe.regional.pakistan, {
	get_formatted_ntn: function (value) {
		if (frappe.sys_defaults.country != "Pakistan") {
			return value;
		}

		value = cstr(value).toUpperCase();
		value = value.replace(/[^a-zA-Z0-9]+/g, "");

		//0000000-0
		if (value.length >= 7) {
			value = value.slice(0, 7) + "-" + value.slice(7);
		}

		return value;
	},

	format_ntn: function(frm, fieldname) {
		if (frappe.sys_defaults.country != "Pakistan") {
			return;
		}

		let value = frm.doc[fieldname];
		if (value) {
			value = frappe.regional.pakistan.get_formatted_ntn(value);
			frm.doc[fieldname] = value;
			frm.refresh_field(fieldname);
		}
	},

	get_formatted_cnic: function (value) {
		if (frappe.sys_defaults.country != "Pakistan") {
			return value;
		}

		value = cstr(value).toUpperCase();
		value = value.replace(/[^0-9]+/g, "");

		// 00000-0000000-0
		if (value.length >= 12) {
			value = value.slice(0, 12) + "-" + value.slice(12);
		}
		if (value.length >= 5) {
			value = value.slice(0, 5) + "-" + value.slice(5);
		}

		return value;
	},

	format_cnic: function(frm, fieldname) {
		if (frappe.sys_defaults.country != "Pakistan") {
			return;
		}

		let value = frm.doc[fieldname];
		if (value) {
			value = frappe.regional.pakistan.get_formatted_cnic(value);
			frm.doc[fieldname] = value;
			frm.refresh_field(fieldname);
		}
	},

	get_formatted_strn: function (value) {
		if (frappe.sys_defaults.country != "Pakistan") {
			return value;
		}

		value = cstr(value).toUpperCase();
		value = value.replace(/[^a-zA-Z0-9]+/g, "");

		// 00-00-0000-000-00
		if (value.length >= 11) {
			value = value.slice(0, 11) + "-" + value.slice(11);
		}
		if (value.length >= 8) {
			value = value.slice(0, 8) + "-" + value.slice(8);
		}
		if (value.length >= 4) {
			value = value.slice(0, 4) + "-" + value.slice(4);
		}
		if (value.length >= 2) {
			value = value.slice(0, 2) + "-" + value.slice(2);
		}

		return value;
	},

	format_strn: function(frm, fieldname) {
		if (frappe.sys_defaults.country != "Pakistan") {
			return;
		}

		let value = frm.doc[fieldname];
		if (value) {
			value = frappe.regional.pakistan.get_formatted_strn(value);
			frm.doc[fieldname] = value;
			frm.refresh_field(fieldname);
		}
	},

	get_formatted_mobile_no: function (value) {
		if (frappe.sys_defaults.country != "Pakistan") {
			return value;
		}

		value = value.replace(/[^0-9+]+/g, "");

		// do not format international numbers
		if (value.slice(0, 1) === '+' || value.slice(0, 2) === '00') {
			return value;
		}

		// 0000-0000000
		if (value.length >= 4) {
			value = value.slice(0, 4) + "-" + value.slice(4);
			return value;
		}

		return value;
	},
});
