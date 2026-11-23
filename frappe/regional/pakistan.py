import re

import frappe
from frappe import _

mobile_international_prefix = "92"
mobile_local_prefix = "0"

cnic_regex = re.compile(r"^.....-.......-.$")
ntn_regex = re.compile(r"^.......-.$")
strn_regex = re.compile(r"^..-..-....-...-..$")

mobile_regex = re.compile(r"^03\d\d-\d\d\d\d\d\d\d$")


def validate_tax_ids_pakistan(tax_id=None, tax_cnic=None, tax_strn=None):
	if tax_id and not ntn_regex.match(tax_id):
		frappe.throw(_("Invalid NTN {0}. NTN must be in the format #######-#").format(frappe.bold(tax_id)))
	if tax_cnic and not cnic_regex.match(tax_cnic):
		frappe.throw(
			_("Invalid CNIC {0}. CNIC must be in the format #####-#######-#").format(frappe.bold(tax_cnic))
		)
	if tax_strn and not strn_regex.match(tax_strn):
		frappe.throw(
			_("Invalid STRN {0}. STRN must be in the format ##-##-####-###-##").format(frappe.bold(tax_strn))
		)


def validate_mobile_pakistan(mobile_no, throw=True):
	if not mobile_no:
		return False

	# do not check mobile number validity for international numbers
	if mobile_no[:1] == "+" or mobile_no[:2] == "00":
		return True

	if not mobile_regex.match(mobile_no):
		if throw:
			frappe.throw(_("Invalid Mobile No. Pakistani Mobile Nos must be in the format 03##-#######"))

		return False

	return True
