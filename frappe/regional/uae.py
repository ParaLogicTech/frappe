import re

import frappe
from frappe import _

mobile_international_prefix = "971"
mobile_local_prefix = "0"

mobile_regex = re.compile(r"^(?:\+971|00971|0)(?:50|52|53|54|55|56|57|58)[0-9]{7}$")
trn_regex = re.compile(r"^\d{15}$")
emirates_id_regex = re.compile(r"^\d{3}-\d{4}-\d{7}-\d$")


def validate_mobile_uae(mobile_no, throw=True):
	if not mobile_no:
		return False

	if (mobile_no[:1] == "+" and mobile_no[:4] != "+971") or (
		mobile_no[:2] == "00" and mobile_no[:5] != "00971"
	):
		return True

	if not mobile_regex.match(mobile_no):
		if throw:
			frappe.throw(_("Invalid UAE Mobile No {0}").format(mobile_no))

		return False

	return True


def validate_tax_ids_uae(tax_id=None, tax_cnic=None):
	if tax_id and not trn_regex.match(tax_id):
		frappe.throw(_("Invalid TRN No {0}. TRN No must contain only 15 digits").format(frappe.bold(tax_id)))
	if tax_cnic and not emirates_id_regex.match(tax_cnic):
		frappe.throw(
			_("Invalid Emirates ID {0}. Emirates ID must be in the format ###-####-#######-#").format(
				frappe.bold(tax_cnic)
			)
		)
