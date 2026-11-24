frappe.ui.form.ControlDynamicLink = class ControlDynamicLink extends frappe.ui.form.ControlLink {
	get_options() {
		const route = frappe.get_route();
		let options = "";
		if (this.df.get_options) {
			options = this.df.get_options(this);
		} else if (this.docname == null && cur_dialog) {
			//for dialog box
			options = cur_dialog.get_value(this.df.options);
		} else if (cur_frm && route && route[0] === "Form") {
			options = frappe.model.get_value(this.df.parent, this.docname, this.df.options);
		} else if (frappe.query_report && route && route[0] == "query-report") {
			options = frappe.query_report.get_filter_value(this.df.options);
		} else {
			const selector = `input[data-fieldname="${this.df.options}"], select[data-fieldname="${this.df.options}"]`;
			let input = null;
			if (cur_list) {
				// for list page
				input = cur_list.filter_area.standard_filters_wrapper.find(selector);
			}

			if (cur_page && !input) {
				input = $(cur_page.page).find(selector);
			}

			if (input) {
				options = input.val();
			}
		}

		if (frappe.model.is_single(options)) {
			frappe.throw(__("{0} is not a valid DocType for Dynamic Link", [options.bold()]));
		}

		return options;
	}
};
