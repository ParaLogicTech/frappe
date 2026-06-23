frappe.ui.form.ControlInt = class ControlInt extends frappe.ui.form.ControlData {
	static trigger_change_on_input_event = false;
	static input_mode = "numeric";
	make() {
		super.make();
	}
	make_input() {
		super.make_input();
		this.$input.on("focus", () => {
			if (!document || !document.activeElement || !document.activeElement.select) return;
			document.activeElement.value = this.validate(document.activeElement.value);
			document.activeElement.select();
			return false;
		});
	}
	validate(value) {
		return this.parse(value);
	}
	eval_expression(value) {
		if (typeof value === "string") {
			value = strip(value);
			if (value.match(/^[0-9+\-/* \t.,()]+$/)) {
				value = strip_number_groups(value);
				// If it is a string containing operators
				try {
					return eval(value);
				} catch (e) {
					// bad expression
					return value;
				}
			}
		}
		return value;
	}
	parse(value) {
		return cint(this.eval_expression(value), null);
	}
};

frappe.ui.form.ControlLongInt = frappe.ui.form.ControlInt;
