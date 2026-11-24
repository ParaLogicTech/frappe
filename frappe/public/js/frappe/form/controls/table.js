import Grid from "../grid";

frappe.ui.form.ControlTable = class ControlTable extends frappe.ui.form.Control {
	make() {
		super.make();

		// add title if prev field is not column / section heading or html
		this.grid = new Grid({
			frm: this.frm,
			df: this.df,
			parent: this.wrapper,
			control: this,
		});

		if (this.frm) {
			this.frm.grids[this.frm.grids.length] = this;
		}

		this.$wrapper.on("paste", ":text", function (e) {
			var dialog = cur_dialog;
			var frm = cur_frm;

			var cur_table_field = $(e.target)
				.closest('div [data-fieldtype="Table"]')
				.data("fieldname");
			var cur_field = $(e.target).data("fieldname");
			var cur_grid = (dialog || frm).get_field(cur_table_field).grid;
			var cur_grid_rows = cur_grid.grid_rows;
			var cur_doctype = cur_grid.doctype;
			var row_idx = $(e.target).closest("div .grid-row").data("idx");
			var clipboardData, pastedData;

			// Get pasted data via clipboard API
			clipboardData =
				e.clipboardData || window.clipboardData || e.originalEvent.clipboardData;
			pastedData = clipboardData.getData("Text");
			if (typeof pastedData === "string") {
				pastedData = strip(pastedData);
			}
			if (!pastedData) return;

			var data = frappe.utils.csv_to_array(pastedData, "\t");
			if (data.length === 1 && (typeof data[0] == "string" || data[0].length === 1)) return;

			var fieldnames = [];
			var get_field = function (name_or_label) {
				var fieldname;
				$.each(cur_grid.docfields, (ci, field) => {
					name_or_label = name_or_label.toLowerCase();
					if (
						field.fieldname.toLowerCase() === name_or_label ||
						(field.label && field.label.toLowerCase() === name_or_label)
					) {
						fieldname = field.fieldname;
						return false;
					}
				});
				return fieldname;
			};

			if (get_field(data[0][0])) {
				// for raw data with column header
				$.each(data[0], (ci, column) => {
					fieldnames.push(get_field(column));
				});
				data.shift();
			} else {
				// no column header, map to the existing visible columns
				var visible_columns = cur_grid_rows[0].get_visible_columns();
				var find;
				$.each(visible_columns, (ci, column) => {
					if (column.fieldname === cur_field) find = true;
					find && fieldnames.push(column.fieldname);
				});
			}

			$.each(data, function (i, row) {
				var blank_row = true;
				$.each(row, function (ci, value) {
					if (value) {
						blank_row = false;
						return false;
					}
				});
				if (!blank_row) {
					if (row_idx > cur_grid_rows.length) {
						cur_grid.add_new_row();
					}
					var cur_row = cur_grid_rows[row_idx - 1];
					row_idx++;
					var row_name = cur_row.doc.name;
					frappe.show_progress(__("Processing"), i, data.length);
					$.each(row, function (ci, value) {
						if (fieldnames[ci]) {
							var fieldtype = cur_grid.fields_map[fieldnames[ci]].fieldtype;
							var parsed_value = value;
							if (["Check", "Int"].includes(fieldtype)) {
								parsed_value = cint(value);
							} else if (frappe.model.numeric_fieldtypes.includes(fieldtype)) {
								parsed_value = flt(value);
							} else if (fieldtype == "Date") {
								parsed_value = frappe.datetime.guess_to_str(value);
							}

							if (dialog) {
								dialog.get_field(cur_table_field).df.get_data()[
									cur_row.doc.idx - 1
								][fieldnames[ci]] = parsed_value;
							} else {
								frappe.model.set_value(
									cur_doctype,
									row_name,
									fieldnames[ci],
									parsed_value
								);
							}
						}
					});
				}
			});

			if (dialog) {
				dialog.get_field(cur_table_field).grid.refresh();
			}
			frappe.hide_progress();
			return false; // Prevent the default handler from running.
		});
	}
	get_field(field_name) {
		let fieldname;
		field_name = field_name.toLowerCase();
		this.grid?.meta?.fields.some((field) => {
			if (frappe.model.no_value_type.includes(field.fieldtype)) {
				return false;
			}

			const is_field_matching = () => {
				return (
					field.fieldname.toLowerCase() === field_name ||
					(field.label || "").toLowerCase() === field_name ||
					(__(field.label, null, field.parent) || "").toLowerCase() === field_name
				);
			};

			if (is_field_matching()) {
				fieldname = field.fieldname;
				return true;
			}
		});
		return fieldname;
	}
	refresh_input() {
		this.grid.refresh();
	}
	get_value() {
		if (this.grid) {
			return this.grid.get_data();
		}
	}
	set_input() {
		//
	}
	validate() {
		return this.get_value();
	}
	check_all_rows() {
		this.$wrapper.find(".grid-row-check")[0].click();
	}
};
