# Copyright (c) 2017, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import frappe
from frappe.contacts.doctype.contact.contact import get_full_name
from frappe.email import get_contact_list
from frappe.tests.utils import FrappeTestCase, timeout
from frappe.utils import cint

test_dependencies = ["Contact", "Salutation"]


class TestContact(FrappeTestCase):
	def test_check_default_email(self):
		emails = [
			{"email": "test1@example.com", "is_primary": 0},
			{"email": "test2@example.com", "is_primary": 0},
			{"email": "test3@example.com", "is_primary": 0},
			{"email": "test4@example.com", "is_primary": 1},
			{"email": "test5@example.com", "is_primary": 0},
		]
		contact = create_contact("Email", "Mr", emails=emails)

		self.assertEqual(contact.email_id, "test4@example.com")

	def test_check_default_phone_and_mobile(self):
		phones = [
			{"phone": "+91 0000000000", "is_primary_phone": 0, "is_primary_mobile_no": 0},
			{"phone": "+91 0000000001", "is_primary_phone": 0, "is_primary_mobile_no": 0},
			{"phone": "+91 0000000002", "is_primary_phone": 1, "is_primary_mobile_no": 0},
			{"phone": "+91 0000000003", "is_primary_phone": 0, "is_primary_mobile_no": 1},
		]
		contact = create_contact("Phone", "Mr", phones=phones)

		self.assertEqual(contact.phone, "+91 0000000002")
		self.assertEqual(contact.mobile_no, "+91 0000000003")

	def test_get_full_name(self):
		self.assertEqual(get_full_name(first="John"), "John")
		self.assertEqual(get_full_name(last="Doe"), "Doe")
		self.assertEqual(get_full_name(company="Doe Pvt Ltd"), "Doe Pvt Ltd")
		self.assertEqual(get_full_name(first="John", last="Doe"), "John Doe")
		self.assertEqual(get_full_name(first="John", middle="Jane"), "John Jane")
		self.assertEqual(get_full_name(first="John", last="Doe", company="Doe Pvt Ltd"), "John Doe")
		self.assertEqual(
			get_full_name(first="John", middle="Jane", last="Doe", company="Doe Pvt Ltd"),
			"John Jane Doe",
		)

	def test_get_contact_list(self):
		# First time from database
		results = get_contact_list("_Test Supplier")
		self.assertEqual(results[0].label, "test_contact@example.com")
		self.assertEqual(results[0].value, "test_contact@example.com")
		self.assertEqual(results[0].description, "_Test Contact For _Test Supplier")

		# Second time from cache
		results = get_contact_list("_Test Supplier")
		self.assertEqual(results[0].label, "test_contact@example.com")
		self.assertEqual(results[0].value, "test_contact@example.com")
		self.assertEqual(results[0].description, "_Test Contact For _Test Supplier")

	def test_only_one_primary_contact_per_link(self):
		first_contact = create_contact("First Primary Contact", "Mr", save=False)
		first_contact.is_primary_contact = 1
		first_contact.append("links", {"link_doctype": "User", "link_name": "Administrator"})
		first_contact.insert()

		second_contact = create_contact("Second Primary Contact", "Mr", save=False)
		second_contact.is_primary_contact = 1
		second_contact.append("links", {"link_doctype": "User", "link_name": "Administrator"})
		second_contact.insert()

		self.assertFalse(first_contact.reload().is_primary_contact)
		self.assertTrue(second_contact.is_primary_contact)

	def test_promoting_contact_clears_existing_primary_contact(self):
		first_contact = create_contact("Existing Primary Contact", "Mr", save=False)
		first_contact.is_primary_contact = 1
		first_contact.append("links", {"link_doctype": "User", "link_name": "Administrator"})
		first_contact.insert()

		second_contact = create_contact("Promoted Primary Contact", "Mr", save=False)
		second_contact.append("links", {"link_doctype": "User", "link_name": "Administrator"})
		second_contact.insert()
		second_contact.is_primary_contact = 1
		second_contact.save()

		self.assertFalse(first_contact.reload().is_primary_contact)
		self.assertTrue(second_contact.is_primary_contact)

	@timeout(5, "Primary Contact validation did not lock the linked party")
	def test_primary_contact_locks_linked_party(self):
		contact = create_contact("Locking Primary Contact", "Mr", save=False)
		contact.is_primary_contact = 1
		contact.append("links", {"link_doctype": "User", "link_name": "Administrator"})

		with self.primary_connection():
			contact.insert()

			with self.secondary_connection():
				self.assertRaises(
					frappe.QueryTimeoutError,
					lambda: frappe.db.get_value("User", "Administrator", for_update=True, wait=False),
				)

	def test_primary_contact_fetches_existing_primaries_once(self):
		contact = create_contact("Multi-link Primary Contact", "Mr", save=False)
		contact.is_primary_contact = 1
		contact.append("links", {"link_doctype": "User", "link_name": "Administrator"})
		contact.append("links", {"link_doctype": "User", "link_name": "Guest"})

		with self.assertQueryCount(2):
			contact.validate_primary_contact()

	def test_clean_contact_name(self):
		contact = frappe.get_doc(
			doctype="Contact", first_name=" John\xa0 ", middle_name="  Quincy ", last_name=" "
		).insert()

		self.assertEqual((contact.first_name, contact.middle_name, contact.last_name), ("John", "", "Quincy"))
		self.assertEqual(contact.full_name, "John Quincy")

	def test_remove_duplicate_emails_and_phones(self):
		contact = frappe.new_doc("Contact", first_name="Duplicates")
		for email_id in ("dup1@example.com", " dup1@example.com", "dup2@example.com"):
			contact.append("email_ids", {"email_id": email_id})
		for phone in ("+971501234567", "+971501234567 ", "+971501234568"):
			contact.append("phone_nos", {"phone": phone})
		contact.insert()

		self.assertEqual(
			[(d.idx, d.email_id) for d in contact.email_ids],
			[(1, "dup1@example.com"), (2, "dup2@example.com")],
		)
		self.assertEqual(
			[(d.idx, d.phone) for d in contact.phone_nos], [(1, "+971501234567"), (2, "+971501234568")]
		)

	def test_primary_and_secondary_email(self):
		# from the fields to the table
		contact = frappe.get_doc(
			doctype="Contact", first_name="Emails", email_id_2="second@example.com"
		).insert()
		self.assertEqual((contact.email_id, contact.email_id_2), ("second@example.com", ""))

		contact.email_id_2 = "third@example.com"
		contact.save()
		self.assertEqual(
			[(d.email_id, d.is_primary) for d in contact.email_ids],
			[("second@example.com", 1), ("third@example.com", 0)],
		)

		# a new primary email replaces the old one in the table
		contact.email_id = "first@example.com"
		contact.save()
		self.assertEqual(
			[(d.email_id, d.is_primary) for d in contact.email_ids],
			[("third@example.com", 0), ("first@example.com", 1)],
		)

		# from the table to the fields
		contact = frappe.new_doc("Contact", first_name="Email Table")
		contact.append("email_ids", {"email_id": "one@example.com"})
		contact.append("email_ids", {"email_id": "two@example.com"})
		contact.insert()
		self.assertEqual((contact.email_id, contact.email_id_2), ("one@example.com", "two@example.com"))
		self.assertEqual([d.is_primary for d in contact.email_ids], [1, 0])

	def test_primary_and_secondary_numbers(self):
		contact = frappe.get_doc(
			doctype="Contact",
			first_name="Numbers",
			mobile_no="+971501234567",
			mobile_no_2="+971501234567",
			phone="+97142345678",
		).insert()
		self.assertEqual(contact.mobile_no_2, "")
		self.assertEqual(
			get_number_rows(contact),
			[("+971501234567", 1, 0), ("+97142345678", 0, 1)],
		)

		contact.mobile_no = "+971501234568"
		contact.mobile_no_2 = "+971501234567"
		contact.save()
		self.assertCountEqual(
			get_number_rows(contact),
			[("+971501234567", 1, 0), ("+97142345678", 0, 1), ("+971501234568", 1, 0)],
		)

		# a new number replaces the old one in the table
		contact.phone = "+97142345679"
		contact.save()
		self.assertCountEqual(
			[d.phone for d in contact.phone_nos], ["+971501234567", "+971501234568", "+97142345679"]
		)

		# from the table to the fields
		contact = frappe.new_doc("Contact", first_name="Number Table")
		contact.append("phone_nos", {"phone": "+971501234567", "is_primary_mobile_no": 1})
		contact.append("phone_nos", {"phone": "+971501234568", "is_primary_mobile_no": 1})
		contact.append("phone_nos", {"phone": "+97142345678", "is_primary_phone": 1})
		contact.insert()
		self.assertEqual(
			(contact.mobile_no, contact.mobile_no_2, contact.phone),
			("+971501234567", "+971501234568", "+97142345678"),
		)

	def test_regional_validation(self):
		previous_country = frappe.db.get_default("country")
		frappe.db.set_default("country", "Pakistan")
		self.addCleanup(frappe.db.set_default, "country", previous_country)

		def new_contact(**values):
			return frappe.get_doc(doctype="Contact", first_name="Regional", **values)

		self.assertRaises(frappe.ValidationError, new_contact(mobile_no="03001234567").insert)
		self.assertRaises(
			frappe.ValidationError, new_contact(mobile_no="0300-1234567", tax_cnic="12345-1234567").insert
		)

		# a landline marked as mobile number loses the mark
		contact = new_contact(
			mobile_no="0300-1234567", mobile_no_2="0301-1234567", tax_cnic="12345-1234567-1"
		)
		contact.append("phone_nos", {"phone": "042-1234567", "is_primary_mobile_no": 1})
		contact.insert()
		self.assertEqual(
			get_number_rows(contact),
			[("042-1234567", 0, 0), ("0300-1234567", 1, 0), ("0301-1234567", 1, 0)],
		)


def get_number_rows(contact):
	return [(d.phone, cint(d.is_primary_mobile_no), cint(d.is_primary_phone)) for d in contact.phone_nos]


def create_contact(name, salutation, emails=None, phones=None, save=True):
	doc = frappe.get_doc(
		{"doctype": "Contact", "first_name": name, "status": "Open", "salutation": salutation}
	)

	if emails:
		for d in emails:
			doc.add_email(d.get("email"), d.get("is_primary"))

	if phones:
		for d in phones:
			doc.add_phone(d.get("phone"), d.get("is_primary_phone"), d.get("is_primary_mobile_no"))

	if save:
		doc.insert()

	return doc
