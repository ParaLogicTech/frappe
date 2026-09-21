# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class PrintFormatSignatory(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		optional: DF.Check
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		pen_color: DF.Color | None
		signatory: DF.Data
		signatory_name_field: DF.Data | None
		signatory_role: DF.Link | None
	# end: auto-generated types
	pass
