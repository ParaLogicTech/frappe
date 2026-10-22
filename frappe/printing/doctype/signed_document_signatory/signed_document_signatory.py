# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class SignedDocumentSignatory(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		signatory: DF.Data
		signatory_email: DF.Data | None
		signatory_mobile: DF.Data | None
		signatory_name: DF.Data | None
		signature_timestamp: DF.Datetime | None
	# end: auto-generated types
	pass
