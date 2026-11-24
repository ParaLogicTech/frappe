frappe.provide("frappe.regional.pakistan");

Object.assign(frappe.regional.pakistan, {
	get_formatted_ntn: function (value) {
		value = cstr(value).toUpperCase();
		value = value.replace(/[^a-zA-Z0-9]+/g, "");

		//0000000-0
		if (value.length >= 7) {
			value = value.slice(0, 7) + "-" + value.slice(7);
		}

		return value;
	},

	get_formatted_cnic: function (value) {
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

	get_formatted_strn: function (value) {
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

	get_formatted_mobile_no: function (value) {
		value = value.replace(/[^0-9+]+/g, "");

		// do not format international numbers
		if (value.slice(0, 1) === "+" || value.slice(0, 2) === "00") {
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
