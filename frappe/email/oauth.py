import base64
from imaplib import IMAP4
from poplib import POP3
from smtplib import SMTP
from typing import Union
from urllib.parse import quote

import frappe
from frappe.integrations.google_oauth import GoogleOAuth
from frappe.utils import get_request_site_address


class OAuthenticationError(Exception):
	pass


class Oauth:
	def __init__(
		self,
		conn: Union[IMAP4, POP3, SMTP],
		email_account: str,
		email: str,
		access_token: str,
		refresh_token: str,
		service: str,
		mechanism: str = "XOAUTH2",
	) -> None:

		self.email_account = email_account
		self.email = email
		self.service = service
		self._mechanism = mechanism
		self._conn = conn
		self._access_token = access_token
		self._refresh_token = refresh_token

		self._validate()

	def _validate(self) -> None:
		if self.service != "GMail":
			raise NotImplementedError(
				f"Service {self.service} currently doesn't have oauth implementation."
			)

		if not self._refresh_token:
			frappe.throw(
				frappe._("Please Authorize OAuth."),
				OAuthenticationError,
				frappe._("OAuth Error"),
			)

	@property
	def _auth_string(self) -> str:
		return "user=%s\1auth=Bearer %s\1\1" % (self.email, self._access_token)

	def connect(self, _retry: int = 0) -> None:
		"""Connection method with retry on exception for Oauth"""
		try:
			if isinstance(self._conn, POP3):
				res = self._connect_pop()

				if not res.startswith(b"+OK"):
					raise

			elif isinstance(self._conn, IMAP4):
				self._connect_imap()

			else:
				# SMTP
				self._connect_smtp()

		except Exception:
			# maybe the access token expired - refreshing
			access_token = self._refresh_access_token()

			if not access_token or _retry > 0:
				frappe.throw(
					frappe._("Authentication Failed. Please Check and Update the credentials."),
					OAuthenticationError,
					frappe._("OAuth Error"),
				)

			self._access_token = access_token
			self.connect(_retry + 1)

	def _connect_pop(self) -> bytes:
		# poplib doesn't have AUTH command implementation
		res = self._conn._shortcmd(
			"AUTH {0} {1}".format(
				self._mechanism, base64.b64encode(bytes(self._auth_string, "utf-8")).decode("utf-8")
			)
		)

		return res

	def _connect_imap(self) -> None:
		self._conn.authenticate(self._mechanism, lambda x: self._auth_string)

	def _connect_smtp(self) -> None:
		self._conn.auth(self._mechanism, lambda x: self._auth_string, initial_response_ok=False)

	def _refresh_access_token(self) -> str:
		"""Refreshes access token via calling `refresh_access_token` method of oauth service object"""
		service_obj = self._get_service_object()
		access_token = service_obj.refresh_access_token(self._refresh_token).get("access_token", None)

		# set the new access token in db
		frappe.db.set_value("Email Account", self.email_account, "access_token", access_token)
		frappe.db.commit()
		return access_token

	def _get_service_object(self):
		"""Get Oauth service object"""

		return {
			"GMail": GoogleOAuth("mail", validate=False),
		}[self.service]


@frappe.whitelist(methods=["POST"])
def oauth_access(email_account: str, service: str = None):
	"""Used as a default endpoint/caller for all oauth services.
	Returns authorization url for redirection"""

	if not service:
		frappe.throw(frappe._("No Service is selected. Please select one and try again!"))

	doctype = "Email Account"

	# NOTE: setting this here, since we redirect to the service's auth page,
	# we lose the use_oauth value in the emal account form
	frappe.db.set_value(doctype, email_account, "use_oauth", 1)

	if service == "GMail":
		return authorize_google_access(email_account, doctype)


def authorize_google_access(email_account, doctype: str = "Email Account", code: str = None):
	"""Facilitates google oauth for email.
	This is invoked 2 times - first time when user clicks `Authorze API Access` for getting the authorization url
	and second time for setting the refresh and access token in db when google redirects back with oauth code."""

	oauth_obj = GoogleOAuth("mail")

	if not code:
		return oauth_obj.get_authentication_url(
			get_request_site_address(True),
			state={
				"method": "frappe.email.oauth.authorize_google_access",
				"redirect": "/app/Form/{0}/{1}".format(quote(doctype), quote(email_account)),
				"email_account": email_account,
			},
		)

	res = oauth_obj.authorize(code, get_request_site_address(True))
	frappe.db.set_value(doctype, email_account, "refresh_token", res.get("refresh_token"))
	frappe.db.set_value(doctype, email_account, "access_token", res.get("access_token"))
