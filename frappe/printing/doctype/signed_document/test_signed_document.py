# Copyright (c) 2026, Frappe Technologies and Contributors
# See license.txt

from io import BytesIO
from unittest.mock import patch

from PIL import Image
from pypdf import PdfWriter

import frappe
from frappe.printing.doctype.signed_document.signed_document import (
	data_url_to_image,
	get_permission_query_conditions,
	has_permission,
	image_to_data_url,
	sign_pdf,
	trim_image,
)
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, now_datetime, set_request

PRINT_FORMAT = "_Test Signature Print Format"
PRINT_FORMAT_HTML = """
<p>{{ doc.description }}</p>
{% for signatory in ("Customer", "Manager") %}
<div class="signature-field" data-fieldtype="Image" data-signatory="{{ signatory }}"></div>
<div class="signature-field" data-fieldtype="Name" data-signatory="{{ signatory }}"></div>
<div class="signature-field" data-fieldtype="Date" data-signatory="{{ signatory }}"></div>
{% endfor %}
"""


def make_blank_pdf():
	writer = PdfWriter()
	writer.add_blank_page(width=100, height=100)
	pdf = BytesIO()
	writer.write(pdf)
	return pdf.getvalue()


BLANK_PDF = make_blank_pdf()


def make_signature(size=(40, 20), border=10, background=(255, 255, 255, 255)):
	"""A black signature inside a border of the background colour"""
	image = Image.new("RGBA", (size[0] + 2 * border, size[1] + 2 * border), background)
	image.paste((0, 0, 0, 255), (border, border, border + size[0], border + size[1]))
	return image


class TestSignedDocument(FrappeTestCase):
	def setUp(self):
		set_request(method="POST", path="/api/method/sign_pdf", headers={"User-Agent": "Test Agent"})
		frappe.get_doc(doctype="Role", role_name="_Test Signing Role").insert(ignore_if_duplicate=True)
		if not frappe.db.exists("Print Format", PRINT_FORMAT):
			frappe.get_doc(
				doctype="Print Format",
				name=PRINT_FORMAT,
				doc_type="ToDo",
				module="Core",
				custom_format=1,
				print_format_type="Jinja",
				html=PRINT_FORMAT_HTML,
				signatories=[
					{"signatory": "Customer"},
					{"signatory": "Manager", "signatory_role": "_Test Signing Role", "optional": 1},
				],
			).insert()

		self.todo = frappe.get_doc(doctype="ToDo", description="Test signing").insert()

	def get_signature_data(self, **values):
		return [
			{
				"signatory": "Customer",
				"signatory_name": "Web Customer",
				"signature_timestamp": "2026-01-02 10:30:00",
				"signature_image": image_to_data_url(make_signature()),
				"signatory_email": "customer@example.com",
				**values,
			}
		]

	def sign(self, signature_data):
		return sign_pdf("ToDo", self.todo.name, signature_data, format=PRINT_FORMAT)

	@patch("frappe.printing.doctype.signed_document.signed_document.get_pdf", return_value=BLANK_PDF)
	def test_sign_pdf(self, get_pdf):
		file_url = self.sign(self.get_signature_data())

		html = get_pdf.call_args.args[0]
		self.assertIn(">Web Customer<", html)
		self.assertIn(f">{frappe.utils.format_date('2026-01-02')}<", html)
		self.assertIn('<img src="data:image/png;base64,', html)
		# the manager didn't sign
		self.assertIn('data-fieldtype="Name" data-signatory="Manager"></div>', html)

		signed_document = frappe.get_last_doc("Signed Document", {"document_name": self.todo.name})
		self.assertTrue(signed_document.name.startswith(f"{self.todo.name}-"))
		self.assertEqual(signed_document.signed_pdf, file_url)
		self.assertEqual(signed_document.print_format, PRINT_FORMAT)
		self.assertEqual(signed_document.user_agent, "Test Agent")
		self.assertFalse(signed_document.digitally_signed)
		self.assertEqual(
			[(d.signatory, d.signatory_name, d.signatory_email) for d in signed_document.signatories],
			[("Customer", "Web Customer", "customer@example.com")],
		)

		file = frappe.get_doc("File", {"file_url": file_url})
		self.assertTrue(file.is_private)
		self.assertEqual(file.get_content(), BLANK_PDF)

	@patch("frappe.printing.doctype.signed_document.signed_document.get_pdf", return_value=BLANK_PDF)
	def test_signature_validation(self, get_pdf):
		for signature_data, error in (
			(self.get_signature_data(signatory="Witness"), "not allowed in print format"),
			(self.get_signature_data(signatory=None), "Signatory not provided"),
			(self.get_signature_data(signatory_name=None), "Name is mandatory"),
			(self.get_signature_data(signature_timestamp=None), "Timestamp not provided"),
			(self.get_signature_data(signature_image=None), "Signature is mandatory"),
			(self.get_signature_data(signature_image="not an image"), "Invalid signature image"),
			(
				self.get_signature_data(signature_timestamp=add_days(now_datetime(), 1)),
				"cannot be in the future",
			),
			([], "No signature data provided"),
		):
			with self.subTest(error=error):
				self.assertRaisesRegex(frappe.ValidationError, error, self.sign, signature_data)

		get_pdf.assert_not_called()

	@patch("frappe.printing.doctype.signed_document.signed_document.get_pdf", return_value=BLANK_PDF)
	def test_signatory_role(self, get_pdf):
		manager = {
			"signatory": "Manager",
			"signatory_name": "Manager",
			"signature_timestamp": "2026-01-02 10:30:00",
			"signature_image": image_to_data_url(make_signature()),
		}
		frappe.set_user("test@example.com")
		self.addCleanup(frappe.set_user, "Administrator")
		self.assertRaises(frappe.PermissionError, self.sign, [*self.get_signature_data(), manager])

		# an optional signatory without a signature is dropped
		manager.pop("signature_image")
		self.sign([*self.get_signature_data(), manager])
		signed_document = frappe.get_last_doc("Signed Document", {"document_name": self.todo.name})
		self.assertEqual([d.signatory for d in signed_document.signatories], ["Customer"])

	def test_trim_image(self):
		# by a solid border
		self.assertEqual(trim_image(make_signature()).size, (40, 20))
		# by a transparent border
		self.assertEqual(trim_image(make_signature(background=(255, 255, 255, 0))).size, (40, 20))
		# a blank image stays as it is
		self.assertEqual(trim_image(Image.new("RGBA", (30, 30), "white")).size, (30, 30))

		data_url = image_to_data_url(make_signature())
		self.assertTrue(data_url.startswith("data:image/png;base64,"))
		self.assertEqual(data_url_to_image(data_url).size, (60, 40))
		self.assertEqual(data_url_to_image(data_url.split(",", 1)[1]).size, (60, 40))

	def test_permissions(self):
		signed_document = frappe.get_doc(
			doctype="Signed Document", document_type="ToDo", document_name=self.todo.name
		)

		self.assertTrue(has_permission(signed_document, "write", user="Administrator"))
		self.assertFalse(has_permission(signed_document, "write", user="test@example.com"))
		# reading follows the signed document
		self.assertEqual(
			has_permission(signed_document, "read", user="test1@example.com"),
			self.todo.has_permission("read", user="test1@example.com"),
		)
		signed_document.document_name = "_Test No Such ToDo"
		self.assertFalse(has_permission(signed_document, "read", user="test@example.com"))

		self.assertEqual(get_permission_query_conditions("Administrator"), "")
		self.assertIn("`document_type` IN (", get_permission_query_conditions("test@example.com"))
		self.assertIn("`owner` = 'Guest'", get_permission_query_conditions("Guest"))
