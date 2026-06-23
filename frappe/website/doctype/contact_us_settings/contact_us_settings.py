# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.model.document import Document
from frappe.utils import clean_whitespace


class ContactUsSettings(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		address_line1: DF.Data | None
		address_line2: DF.Data | None
		address_title: DF.Data | None
		city: DF.Data | None
		country: DF.Data | None
		email_id: DF.Data | None
		forward_to_email: DF.Data | None
		heading: DF.Data | None
		introduction: DF.TextEditor | None
		is_disabled: DF.Check
		phone: DF.Data | None
		pincode: DF.Data | None
		query_options: DF.SmallText | None
		skype: DF.Data | None
		state: DF.Data | None

	# end: auto-generated types
	def validate(self):
		for i, d in enumerate(self.get("query_options")):
			d.option = clean_whitespace(d.option)

		self.query_options = [d for i, d in enumerate(self.query_options) if d or i == 0]
		for i, d in enumerate(self.get("query_options")):
			d.idx = i + 1

	def on_update(self):
		from frappe.website.utils import clear_cache
		clear_cache()


def update_website_context(context):
	doc = frappe.get_cached_doc("Contact Us Settings", None).as_dict()

	doc.query_options_table = doc.query_options

	if doc.query_options:
		doc.query_options = [d.option for i, d in enumerate(doc.query_options) if d]
		if doc.do_not_set_default_option:
			doc.query_options.insert(0, "")
	else:
		doc.query_options = ["Sales", "Support", "General"]

	context['contact_us_settings'] = doc
