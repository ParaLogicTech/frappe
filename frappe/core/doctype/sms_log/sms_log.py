# Copyright (c) 2022, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class SMSLog(Document):
	def on_trash(self):
		if frappe.session.user != "Administrator":
			frappe.throw(_("Only Administrator can delete SMS Log"))
