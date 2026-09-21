import SignaturePad from "signature_pad";

frappe.provide("frappe.ui.signature_pad");

frappe.ui.signature_pad.SignaturePad = class FrappeSignaturePad extends SignaturePad {
	constructor(canvas, options = {}) {
		super(canvas, options);

		this.signatoryData = options?.signatoryData || {};

		this.resizeObserver = new ResizeObserver((entries) => {
			for (let entry of entries) {
				if (entry.target == this.canvas) {
					this.debouncedResizeCanvas();
				}
			}
		});
		this.resizeObserver.observe(this.canvas);
		this.resizeCanvas();
	}

	debouncedResizeCanvas = frappe.utils.debounce(this.resizeCanvas, 200);

	resizeCanvas() {
		const ratio =  Math.max(window.devicePixelRatio || 1, 1);
		this.canvas.width = (this.canvas.offsetWidth || this.canvas.width) * ratio;
		this.canvas.height = (this.canvas.offsetHeight || this.canvas.height) * ratio;
		this.canvas.getContext("2d").scale(ratio, ratio);
		this.clear();
	}

	clear() {
		super.clear();
		if (this.signatoryData) {
			this.signatoryData.signature_timestamp = null;
		}
	}
};

$.extend(frappe.ui.signature_pad, {
	show_signature_dialog(args) {
		args = args || {};

		let all_signatories = frappe.utils.deep_clone(args.signatories || []);
		let signatories = [];

		for (let signatory_data of all_signatories) {
			if (signatory_data.signatory_role && !frappe.user_roles.includes(signatory_data.signatory_role)) {
				if (signatory_data.optional) {
					continue;
				} else {
					frappe.throw(__("You are not allowed to sign this document"));
				}
			}
			signatories.push(signatory_data);
		}
		if (!signatories.length) {
			return;
		}

		let fields = [];
		for (let [i, signatory_data] of signatories.entries()) {
			let name_field = "signatory_name_" + i;
			let html_field = "signature_area_" + i;

			let signatory_name = signatory_data.signatory_name;
			if (!signatory_name && signatory_data.signatory_name_field && args.doc) {
				signatory_name = args.doc[signatory_data.signatory_name_field];
			}

			fields.push({
				fieldtype: "Section Break",
			});
			fields.push({
				label: `${signatory_data.signatory || ""} ${__("Name")}`,
				fieldtype: "Data",
				fieldname: name_field,
				default: signatory_name || "",
				reqd: signatory_data.optional ? 0 : 1,
			});
			fields.push({
				fieldtype: "HTML",
				fieldname: html_field,
			});
		}

		const dialog = new frappe.ui.Dialog({
			title: args.title || __("Sign"),
			fields: fields,
		});

		let signature_pads = [];
		for (let [i, signatory_data] of signatories.entries()) {
			let html_field = "signature_area_" + i;
			let pad = frappe.ui.signature_pad.add_signature_pad(
				dialog.fields_dict[html_field].$wrapper,
				args,
				signatory_data,
			);
			signature_pads.push(pad);
		}

		dialog.show();

		dialog.set_primary_action(__("Submit"), () => {
			let values = dialog.get_values();
			let output = [];

			for (let [i, pad] of signature_pads.entries()) {
				if (pad.isEmpty() && !pad.signatoryData?.optional) {
					frappe.msgprint({
						message: __("Missing {0} Signature", [pad.signatoryData?.signatory]),
						title: __("Missing Signature"),
						indicator: "yellow",
					});
					return;
				}

				let name_field = "signatory_name_" + i;
				let signatory_name = values[name_field];
				if (!pad.isEmpty() && !signatory_name) {
					frappe.msgprint({
						message: __("Please enter {0} Name", [pad.signatoryData?.signatory]),
						title: __("Missing Values"),
						indicator: "yellow",
					});
					return;
				}

				output.push({
					"signatory": pad.signatoryData?.signatory || "",
					"signatory_name": signatory_name,
					"signature_image": pad.isEmpty() ? null : pad.toDataURL("image/png"),
					"signature_timestamp": pad.signatoryData?.signature_timestamp || null,
				});
			}

			return frappe.run_serially([
				() => args.callback && args.callback(output),
				() => dialog.hide(),
			]);
		});
	},

	add_signature_pad(wrapper, args, signatory_data) {
		signatory_data = signatory_data || {};

		let $wrapper = $(wrapper);

		let $signature_pad_wrapper = $(`<div class="signature-pad-wrapper"></div>`).appendTo($wrapper);

		$signature_pad_wrapper.append(`<div class="control-label ${!signatory_data.optional ? "reqd" : ""}">${signatory_data.signatory || ""} Signature</div>`)
		$signature_pad_wrapper.append(`<div class="signature-pad"></div>`);

		let $signature_pad = $signature_pad_wrapper.find(".signature-pad");
		$signature_pad.append(`<canvas></canvas>`);
		$signature_pad.append(`<div class="signature-pad-background"></div>`);
		$signature_pad.append(`<div class="signature-pad-btn-row"></div>`);

		let $buttons_row = $signature_pad.find(".signature-pad-btn-row");
		$buttons_row.append(`
			<button class="btn btn-default signature-clear">
				${frappe.utils.icon("es-line-reload", "sm")}
				${__("Clear")}
			</button>
		`);

		let $canvas = $signature_pad_wrapper.find("canvas");

		let pad = new frappe.ui.signature_pad.SignaturePad($canvas[0], {
			penColor: signatory_data.pen_color || args.pen_color || "#0047AB",
			signatoryData: signatory_data,
		});

		pad.addEventListener("endStroke", () => {
			pad.signatoryData.signature_timestamp = frappe.datetime.now_datetime();
		});

		$buttons_row.on("click", ".signature-clear", () => {
			pad.clear();
		});

		return pad;
	}
});
