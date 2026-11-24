frappe.provide("frappe.regional.uae");

Object.assign(frappe.regional.uae, {
	get_formatted_mobile_no: function (value) {
		value = value.replace(/[^0-9+]+/g, "");

		// do not format international numbers
		if (
			(value.slice(0, 1) === "+" && value.slice(0, 4) === "+971") ||
			(value.slice(0, 2) === "00" && value.slice(0, 5) === "00971")
		) {
			return value;
		}

		return value;
	},

	get_formatted_trn: function (value) {
		value = cstr(value).toUpperCase();
		value = value.replace(/[^a-zA-Z0-9]+/g, "");
		return value;
	},

	get_formatted_emirates_id: function (value) {
		value = cstr(value).toUpperCase();
		value = value.replace(/[^a-zA-Z0-9]+/g, "");

		// 000-0000-0000000-0
		if (value.length >= 14) {
			value = value.slice(0, 14) + "-" + value.slice(14);
		}
		if (value.length >= 7) {
			value = value.slice(0, 7) + "-" + value.slice(7);
		}
		if (value.length >= 3) {
			value = value.slice(0, 3) + "-" + value.slice(3);
		}

		return value;
	},
});
