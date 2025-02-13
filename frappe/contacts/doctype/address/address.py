# Copyright (c) 2015, Frappe Technologies and contributors
# License: MIT. See LICENSE

from typing import Optional

from jinja2 import TemplateSyntaxError

import frappe
from frappe import _
from frappe.contacts.address_and_contact import set_link_title
from frappe.core.doctype.dynamic_link.dynamic_link import deduplicate_dynamic_links
from frappe.model.document import Document
from frappe.utils import cint, clean_whitespace


class Address(Document):
	def __setup__(self):
		self.flags.linked = False

	def validate(self):
		self.clean_address()
		self.link_address()
		self.validate_preferred_address()
		set_link_title(self)
		deduplicate_dynamic_links(self)

	def before_save(self):
		if not self.address_title:
			if self.links:
				self.address_title = self.links[0].link_title or self.links[0].link_name
				self.address_title = clean_whitespace(self.address_title)

	def on_update(self):
		self.update_primary_address_in_linked_docs()

	def clean_address(self):
		fields = [
			"address_title",
			"address_line1", "address_line2", "address_line3",
			"city", "state", "pincode"
		]

		for f in fields:
			if self.meta.has_field(f) and self.get(f):
				self.set(f, clean_whitespace(self.get(f)))

	def update_primary_address_in_linked_docs(self):
		from frappe.model.base_document import get_controller

		for d in self.links:
			if d.link_doctype and self.flags.from_linked_document != (d.link_doctype, d.link_name):
				try:
					if hasattr(get_controller(d.link_doctype), "update_primary_address"):
						doc = frappe.get_doc(d.link_doctype, d.link_name)
						doc.flags.from_address = True
						doc.flags.pull_address = True
						doc.update_primary_address()
						doc.notify_update()
				except ImportError:
					pass

	def link_address(self):
		"""Link address based on owner"""
		if not self.links:
			contact_name = frappe.db.get_value("Contact", {"email_id": self.owner})
			if contact_name:
				contact = frappe.get_cached_doc("Contact", contact_name)
				for link in contact.links:
					self.append("links", dict(link_doctype=link.link_doctype, link_name=link.link_name))
				return True

		return False

	def validate_preferred_address(self):
		preferred_fields = ["is_primary_address", "is_shipping_address"]

		for field in preferred_fields:
			if self.get(field):
				for link in self.links:
					address = get_preferred_address(link.link_doctype, link.link_name, field)

					if address:
						update_preferred_address(address, field)

	def get_display(self):
		return get_address_display(self.as_dict())

	def has_link(self, doctype, name):
		for link in self.links:
			if link.link_doctype == doctype and link.link_name == name:
				return True

	def has_common_link(self, doc):
		reference_links = [(link.link_doctype, link.link_name) for link in doc.links]
		for link in self.links:
			if (link.link_doctype, link.link_name) in reference_links:
				return True

		return False


def get_preferred_address(doctype, name, preferred_key="is_primary_address"):
	if preferred_key in ["is_shipping_address", "is_primary_address"]:
		address = frappe.db.sql(
			""" SELECT
				addr.name
			FROM
				`tabAddress` addr, `tabDynamic Link` dl
			WHERE
				dl.parent = addr.name and dl.link_doctype = %s and
				dl.link_name = %s and ifnull(addr.disabled, 0) = 0 and
				%s = %s
			"""
			% ("%s", "%s", preferred_key, "%s"),
			(doctype, name, 1),
			as_dict=1,
		)

		if address:
			return address[0].name

	return


@frappe.whitelist()
def get_default_address(
	doctype: str, name: str | None, sort_key: str = "is_primary_address"
) -> str | None:
	"""Returns default Address name for the given doctype, name"""
	if sort_key not in ["is_shipping_address", "is_primary_address"]:
		return None

	addresses = frappe.get_all(
		"Address",
		filters=[
			["Dynamic Link", "link_doctype", "=", doctype],
			["Dynamic Link", "link_name", "=", name],
			["disabled", "=", 0],
		],
		pluck="name",
		order_by=f"{sort_key} DESC",
		limit=1,
	)

	return addresses[0] if addresses else None


@frappe.whitelist()
def get_address_display(address_dict: dict | str | None = None) -> str | None:
	if not address_dict:
		return

	if not isinstance(address_dict, dict):
		address_dict = frappe.db.get_value("Address", address_dict, "*", as_dict=True, cache=True) or {}

	name, template = get_address_templates(address_dict)

	try:
		return frappe.render_template(template, address_dict)
	except TemplateSyntaxError:
		frappe.throw(_("There is an error in your Address Template {0}").format(name))


def get_territory_from_address(address):
	"""Tries to match city, state and country of address to existing territory"""
	if not address:
		return

	if isinstance(address, str):
		address = frappe.get_cached_doc("Address", address)

	territory = None
	for fieldname in ("city", "state", "country"):
		if address.get(fieldname):
			territory = frappe.db.get_value("Territory", address.get(fieldname))
			if territory:
				break

	return territory


def get_list_context(context=None):
	return {
		"title": _("Addresses"),
		"get_list": get_address_list,
		"row_template": "templates/includes/address_row.html",
		"no_breadcrumbs": True,
	}


def get_address_list(doctype, txt, filters, limit_start, limit_page_length=20, fields=None, order_by=None):
	from frappe.www.list import get_list

	user = frappe.session.user
	ignore_permissions = True

	if not filters:
		filters = []

	contact_links = get_contact_links()

	address_names = []
	if contact_links:
		address_names = frappe.db.sql_list("""
			select addr.name
			from `tabDynamic Link` l
			inner join `tabAddress` addr on l.parenttype = 'Address' and l.parent = addr.name
			where (l.link_doctype, l.link_name) in %s
		""", [contact_links])

	if not address_names:
		return []

	filters.append(["Address", "name", "in", address_names])

	return get_list(
		doctype, txt, filters, limit_start, limit_page_length,
		ignore_permissions=ignore_permissions, fields=fields, order_by=order_by,
	)


def has_website_permission(doc, ptype, user, verbose=False):
	"""Returns true if there is a related lead or contact related to this document"""
	address_links = set([(link.link_doctype, link.link_name) for link in doc.links])
	if not address_links:
		return False

	contact_links = set(get_contact_links())

	return bool(contact_links.intersection(address_links))


def get_contact_links():
	return frappe.db.sql("""
		select distinct l.link_doctype, l.link_name
		from `tabDynamic Link` l
		inner join `tabContact` c on l.parenttype = 'Contact' and l.parent = c.name
		where c.user = %s
	""", frappe.session.user)


def get_address_templates(address):
	result = frappe.db.get_value(
		"Address Template", {"country": address.get("country")}, ["name", "template"]
	)

	if not result:
		result = frappe.db.get_value("Address Template", {"is_default": 1}, ["name", "template"])

	if not result:
		from frappe.contacts.doctype.address_template.address_template import get_default_address_template
		return None, get_default_address_template()
	else:
		return result


@frappe.whitelist()
def get_company_address(company, shipping_address=False):
	ret = frappe._dict()

	sort_key = "is_shipping_address" if cint(shipping_address) else "is_primary_address"

	ret.company_address = get_default_address("Company", company, sort_key=sort_key)
	ret.company_address_display = get_address_display(ret.company_address)

	return ret


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def address_query(doctype, txt, searchfield, start, page_len, filters):
	from frappe.desk.reportview import get_match_cond, get_filters_cond

	doctype = "Address"
	link_doctype = filters.pop("link_doctype", None)
	link_name = filters.pop("link_name", None)

	meta = frappe.get_meta(doctype)
	searchfields = meta.get_search_fields()
	if searchfield and searchfield not in searchfields and \
			(meta.get_field(searchfield) or searchfield in frappe.db.DEFAULT_COLUMNS):
		searchfields.append(searchfield)

	fields = ["name"] + searchfields
	fields = frappe.utils.unique(fields)
	fields = ", ".join(["`tabAddress`.{0}".format(f) for f in fields])

	search_condition = " or ".join(["`tabAddress`.{0}".format(field) + " like %(txt)s" for field in searchfields])

	return frappe.db.sql("""
		select {fields}
		from `tabAddress`, `tabDynamic Link`
		where `tabDynamic Link`.parent = `tabAddress`.name
			and `tabDynamic Link`.parenttype = 'Address'
			and `tabDynamic Link`.link_doctype = %(link_doctype)s
			and `tabDynamic Link`.link_name = %(link_name)s
			and `tabAddress`.disabled = 0
			and ({scond})
			{fcond} {mcond}
		order by
			if(locate(%(_txt)s, `tabAddress`.name), locate(%(_txt)s, `tabAddress`.name), 99999),
			if(locate(%(_txt)s, `tabAddress`.address_line1), locate(%(_txt)s, `tabAddress`.address_line1), 99999),
			if(locate(%(_txt)s, `tabAddress`.address_line2), locate(%(_txt)s, `tabAddress`.address_line2), 99999),
			`tabAddress`.idx desc,
			`tabAddress`.name
		limit %(start)s, %(page_len)s
	""".format(
		fields=fields,
		mcond=get_match_cond(doctype),
		scond=search_condition,
		fcond=get_filters_cond(doctype, filters, []),
	), {
		"txt": "%" + txt + "%",
		"_txt": txt.replace("%", ""),
		"start": start,
		"page_len": page_len,
		"link_name": link_name,
		"link_doctype": link_doctype,
	})


def get_condensed_address(doc):
	fields = ["address_title", "address_line1", "address_line2", "city", "county", "state", "country"]
	return ", ".join(doc.get(d) for d in fields if doc.get(d))


def update_preferred_address(address, field):
	frappe.db.set_value("Address", address, field, 0)
