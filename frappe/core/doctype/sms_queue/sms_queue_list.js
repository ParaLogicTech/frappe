frappe.listview_settings["SMS Queue"] = {
	get_indicator: function (doc) {
		let colour = {
			"Not Sent": "grey",
			Sending: "blue",
			Sent: "green",
			"Partially Sent": "purple",
			Error: "red",
			"Partially Errored": "orange",
			Expired: "grey",
		};
		return [__(doc.status), colour[doc.status], "status,=," + doc.status];
	},
};
