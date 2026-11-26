frappe.listview_settings["ToDo"] = {
	hide_name_column: true,
	add_fields: ["reference_type", "reference_name"],

	onload: function (me) {
		// onload also runs in the Report, Kanban and Calendar views, which have titles of their own
		if (me.view_name !== "List") return;
		me.page.set_title(__("To Do"));
	},

	button: {
		show: function (doc) {
			return doc.reference_name;
		},
		get_label: function () {
			return __("Open", null, "Access");
		},
		get_description: function (doc) {
			return __("Open {0}", [`${__(doc.reference_type)}: ${doc.reference_name}`]);
		},
		action: function (doc) {
			frappe.set_route("Form", doc.reference_type, doc.reference_name);
		},
	},
};
