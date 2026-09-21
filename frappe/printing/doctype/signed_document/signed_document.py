# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import cint, get_datetime, format_datetime, format_date, format_time
from frappe.translate import print_language
from frappe.model.document import Document
from frappe.permissions import SYSTEM_USER_ROLE, get_doctypes_with_read
from frappe.utils.pdf import get_pdf
from frappe.www.printview import validate_print_permission
from io import BytesIO
import base64


class SignedDocument(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.printing.doctype.signed_document_signatory.signed_document_signatory import SignedDocumentSignatory
		from frappe.types import DF

		branch_name: DF.Data | None
		company_name: DF.Data | None
		digitally_signed: DF.Check
		document_name: DF.DynamicLink
		document_type: DF.Link
		ip_address: DF.Data | None
		signatories: DF.Table[SignedDocumentSignatory]
		signature_timestamp: DF.Datetime | None
		signed_pdf: DF.Attach | None
		user: DF.Link | None
		user_agent: DF.Data | None
	# end: auto-generated types

	def autoname(self):
		timestamp = get_datetime(self.signature_timestamp)
		timestamp_str = format_datetime(timestamp, "yyMMdd-HHmm")
		self.name = f"{self.document_name}-{timestamp_str}-{frappe.generate_hash(length=4)}"


@frappe.whitelist()
def sign_pdf(
	doctype: str,
	name: str,
	signature_data: str | dict,
	format=None,
	doc=None,
	no_letterhead=0,
	language=None,
	letterhead=None,
	pdf_generator=None,
):
	from bs4 import BeautifulSoup

	doc = doc or frappe.get_doc(doctype, name)
	validate_print_permission(doc)

	if not format:
		frappe.throw("Print Format not provided")

	signature_data = frappe.parse_json(signature_data)

	# validate and check permission
	print_format_doc = frappe.get_doc("Print Format", format)

	signature_data_to_remove = []
	for s in signature_data:
		if not s.get("signatory"):
			frappe.throw(_("Signatory not provided"))

		pf_signatory_row = [d for d in print_format_doc.signatories if d.signatory == s.get("signatory")]
		pf_signatory_row = pf_signatory_row[0] if pf_signatory_row else None
		if not pf_signatory_row:
			frappe.throw(_("Signatory {0} is not allowed in print format {1}").format(
				frappe.bold(s.get("signatory")), format
			))

		if pf_signatory_row.signatory_role and pf_signatory_row.signatory_role not in frappe.get_roles():
			if s.get("signature_image") or not pf_signatory_row.optional:
				frappe.throw(_("You are not allowed to sign for {0}").format(
					pf_signatory_row.signatory
				), exc=frappe.PermissionError)

			if pf_signatory_row.optional:
				signature_data_to_remove.append(s)
				continue

		if s.get("signature_image"):
			if not s.get("signatory_name"):
				frappe.throw(_("{0} Name is mandatory").format(
					frappe.bold(s.get("signatory"))
				))

			if not s.get("signature_timestamp"):
				frappe.throw(_("{0} Signature Timestamp not provided").format(
					frappe.bold(s.get("signatory"))
				))
		else:
			if not pf_signatory_row.optional:
				frappe.throw(_("{0} Signature is mandatory").format(
					frappe.bold(s.get("signatory"))
				))

			s["signature_timestamp"] = None

		if s.get("signature_timestamp"):
			s["signature_timestamp"] = get_datetime(s.get("signature_timestamp"))
			if s.get("signature_timestamp") > get_datetime():
				frappe.throw(_("Signature timestamp cannot be in the future"))

	for s in signature_data_to_remove:
		signature_data.remove(s)

	if not signature_data:
		frappe.throw(_("No signature data provided"))

	with print_language(language):
		html = frappe.get_print(
			doctype,
			name,
			format,
			doc=doc,
			as_pdf=False,
			letterhead=letterhead,
			no_letterhead=no_letterhead,
		)

	# Trim signatures
	try:
		for s in signature_data:
			if not s.get("signature_image") or s.get("skip_trimming"):
				continue

			im = data_url_to_image(s.get("signature_image"))
			im = trim_image(im)
			s["signature_image"] = image_to_data_url(im)
	except Exception:
		frappe.throw(_("Invalid signature image"))

	soup = BeautifulSoup(html, "html.parser")
	for s in signature_data:
		if not s.get("signature_image"):
			continue

		signatory = s.get("signatory") or ""

		if s.get("signatory_name"):
			name_fields = soup.select(f".signature-field[data-fieldtype='Name'][data-signatory='{signatory}']")
			for el in name_fields:
				el.string = s.get("signatory_name")

		if s.get("signature_timestamp"):
			date_fields = soup.select(f".signature-field[data-fieldtype='Date'][data-signatory='{signatory}']")
			time_fields = soup.select(f".signature-field[data-fieldtype='Time'][data-signatory='{signatory}']")
			datetime_fields = soup.select(f".signature-field[data-fieldtype='Datetime'][data-signatory='{signatory}']")
			for el in date_fields:
				el.string = format_date(s.get("signature_timestamp"))
			for el in time_fields:
				el.string = format_time(s.get("signature_timestamp"))
			for el in datetime_fields:
				el.string = format_datetime(s.get("signature_timestamp"))

		if s.get("signature_image"):
			image_fields = soup.select(f".signature-field[data-fieldtype='Image'][data-signatory='{signatory}']")
			for el in image_fields:
				el.clear()
				img = soup.new_tag("img")
				img["src"] = s.get("signature_image")
				img["style"] = "object-fit: scale-down; mix-blend-mode: multiply;"
				el.append(img)

	html = str(soup)
	pdf_file = get_pdf(html)
	pdf_file, digitally_signed = digitally_sign_pdf(pdf_file)
	timestamp = get_datetime()

	request_dict = frappe.request.__dict__
	user_agent = request_dict.get("environ", {}).get("HTTP_USER_AGENT")

	signed_document_doc = frappe.new_doc("Signed Document")
	signed_document_doc.document_type = doctype
	signed_document_doc.document_name = name
	signed_document_doc.company_name = doc.get("company") or doc.get("company_name")
	signed_document_doc.branch_name = doc.get("branch") or doc.get("branch_name")
	signed_document_doc.user = frappe.session.user
	signed_document_doc.ip_address = frappe.local.request_ip
	signed_document_doc.user_agent = user_agent
	signed_document_doc.signature_timestamp = timestamp
	signed_document_doc.digitally_signed = cint(digitally_signed)

	for s in signature_data:
		signed_document_doc.append("signatories", {
			"signatory": s.get("signatory"),
			"signatory_name": s.get("signatory_name"),
			"signature_timestamp": s.get("signature_timestamp"),
			"contact_email": s.get("contact_email"),
			"contact_mobile": s.get("contact_mobile"),
		})

	signed_document_doc.flags.ignore_permissions = True
	signed_document_doc.insert()

	filename = "{name}-signed-{timestamp}.pdf".format(
		name=name.replace(" ", "-").replace("/", "-"),
		timestamp=format_datetime(timestamp, "yyMMdd-HHmmss"),
	)

	file_doc = frappe.new_doc("File")
	file_doc.content = pdf_file
	file_doc.file_name = filename
	file_doc.is_private = 1
	file_doc.attached_to_doctype = signed_document_doc.doctype
	file_doc.attached_to_name = signed_document_doc.name
	file_doc.attached_to_field = "signed_pdf"
	file_doc.save()

	signed_document_doc.db_set("signed_pdf", file_doc.file_url)

	return file_doc.file_url


def trim_image(im):
	from PIL import Image, ImageChops

	# 1. First, try trimming by transparent pixels
	# Converting to premultiplied alpha ('RGBa') handles empty white-transparent pixels correctly
	rgba_im = im.convert("RGBA")
	alpha_bbox = rgba_im.convert("RGBa").getbbox()

	# If a transparent bounding box is found and it actually shrunk the image, use it
	if alpha_bbox and alpha_bbox != (0, 0, im.size[0], im.size[1]):
		return im.crop(alpha_bbox)

	# 2. Fallback: Trim by solid color border (if no transparent pixels were trimmed)
	# Grab the top-left pixel color as the target background color
	bg_color = rgba_im.getpixel((0, 0))
	bg = Image.new("RGBA", im.size, bg_color)

	diff = ImageChops.difference(rgba_im, bg)
	# Amplify differences slightly to eliminate minor JPEG compression noise
	diff = ImageChops.add(diff, diff, 2.0, -100)

	color_bbox = diff.getbbox()
	if color_bbox:
		return im.crop(color_bbox)

	return im  # Return original if the image is entirely one solid color


def data_url_to_image(data_url):
	from PIL import Image

	# Split the metadata prefix out to extract only the Base64 payload
	if "," in data_url:
		header, encoded = data_url.split(",", 1)
	else:
		encoded = data_url

	# Decode the base64 data into memory bytes
	image_bytes = base64.b64decode(encoded)
	img = Image.open(BytesIO(image_bytes))

	return img


def image_to_data_url(im):
	buffered = BytesIO()
	im.save(buffered, format="PNG")
	img_bytes = buffered.getvalue()
	img_base64 = base64.b64encode(img_bytes).decode("utf-8")
	data_url = f"data:image/png;base64,{img_base64}"
	return data_url


def digitally_sign_pdf(unsigned_pdf):
	from frappe.core.doctype.file import get_file_local_path
	from pyhanko.sign import signers
	from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter

	dsc_settings = frappe.get_single("Digital Signature Settings")
	if not dsc_settings.certificate_file:
		return unsigned_pdf, False

	pfx_certificate_path = get_file_local_path(dsc_settings.certificate_file)
	passphrase = dsc_settings.get_password("passphrase")

	signer = signers.SimpleSigner.load_pkcs12(
		pfx_file=pfx_certificate_path,
		passphrase=passphrase.encode('utf-8')
	)

	w = IncrementalPdfFileWriter(BytesIO(unsigned_pdf))
	meta = signers.PdfSignatureMetadata(field_name='Signature1')

	signed_pdf = signers.sign_pdf(w, meta, signer=signer)
	signed_pdf.seek(0)

	return signed_pdf.getvalue(), True


def has_permission(doc, ptype=None, user=None, debug=False):
	user = user or frappe.session.user

	if user == "Administrator":
		return True
	if ptype in ["write", "create", "delete"]:
		return False

	try:
		ref_doc = frappe.get_doc(doc.document_type, doc.document_name)
	except (ModuleNotFoundError, ImportError):
		return False
	except frappe.DoesNotExistError:
		frappe.clear_last_message()
		return False

	return ref_doc.has_permission("read", debug=debug, user=user)


def get_permission_query_conditions(user: str | None = None) -> str:
	user = user or frappe.session.user
	if user == "Administrator":
		return ""

	if SYSTEM_USER_ROLE not in frappe.get_roles(user):
		return f""" `tabSigned Document`.`owner` = {frappe.db.escape(user)} """

	readable_doctypes = ", ".join(frappe.db.escape(dt) for dt in get_doctypes_with_read())
	if readable_doctypes:
		return f""" `tabSigned Document`.`document_type` IN ({readable_doctypes}) """
	else:
		return "1 != 1"
