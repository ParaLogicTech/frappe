import requests
import json
import frappe
from frappe.utils import (now_datetime)
import pytz

class WhatsAppConfiguration:

	def __init__(self):
		self.wa_token = frappe.db.get_single_value("WhatsApp Settings", "wa_token")

	def get_api_url(self):
		wa_api_url =  frappe.db.get_single_value("Whatsapp Settings",'wa_api_url')
		wa_api_version =  frappe.db.get_single_value("Whatsapp Settings",'wa_api_version')
		wa_ph_id =  frappe.db.get_single_value("Whatsapp Settings",'wa_ph_id')
		whatsapp_api =  wa_api_url + "/" + wa_api_version + "/"+ wa_ph_id
		return whatsapp_api

	def send_common_message(self, whatsapp_api, message_template,headers,**kwargs):
		try:
			r = requests.post(whatsapp_api, data=json.dumps(message_template), headers=headers)
		except Exception as e:
			pass

	def now_in_et(self):
		return now_datetime().astimezone(pytz.timezone("America/Toronto"))

	def local_to_international_mobile_no(mobile_nos):
		valid_numbers = []

		for mobile_no in mobile_nos:
			if not mobile_no:
				continue

			mobile_no = mobile_no.strip()
			if not mobile_no:
				continue
			if mobile_no.startswith("00"):
				valid_numbers.append(f"+{mobile_no[2:]}")
			elif mobile_no.startswith("+"):
				valid_numbers.append(mobile_no)
			else:
				valid_numbers.append(f"+1{mobile_no}")

		return valid_numbers

	# FIXME: fetch the message template dynamically then update the references
	def get_price_list_notification_template(self, file_data=None, file_name=None):
		message_template = {"messaging_product":"whatsapp","to":"","type":"template","template":{"name":"ob_alert_route_staff_v1","language":{"code":"en"},"components":[{"type":"header","parameters":[{"type":"document","document":{"id":"","filename":""}}]},{"type":"body","parameters":[{"type":"text","text":""},{"type":"text","text":""}]}]}}

		media_ref_id = self.get_media_reference_id(file_name=file_name, file_data=file_data)

		if not media_ref_id:
			frappe.throw("Error while uploading the media. Please try again. Thank You.")
			return None

		message_template["template"]["components"][0]["parameters"][0]["document"]["id"] = media_ref_id
		message_template["template"]["components"][0]["parameters"][0]["document"]["filename"] = file_name
		message_template["template"]["components"][1]["parameters"][0]["text"] = file_name
		message_template["template"]["components"][1]["parameters"][1]["text"] = self.now_in_et().strftime("%d-%m-%Y at %I:%M %p")

		return message_template

	def get_media_reference_id(self, file_name=None, file_data=None):
		try:
			media_api = self.get_api_url() + "/media"
			media_header = {'Authorization': 'Bearer ' + self.wa_token}

			if not file_name and not file_data :
				return None

			files = {
				'file': (file_name, file_data, 'application/pdf'),
				'type': 'application/pdf',
				'messaging_product': (None, 'whatsapp'),
			}

			media_response = requests.post(media_api, headers=media_header, files=files)

			# TODO: handle the response status codes.
			return media_response.json()["id"]

		except Exception as e:
			frappe.log_error(f"File upload error '{file_name}': {str(e)}", "WhatsApp Media Upload")
			return None

	def send_whatsapp(self, mobile_number=None, file_name=None, file_data=None):
		media_ref_id = self.get_media_reference_id(file_name=file_name, file_data=file_data)
		message_template = self.get_price_list_notification_template(file_data=file_data, file_name=file_name)
		message_template["to"] = mobile_number
		headers = {'content-type': 'application/json','Authorization':'Bearer '+ self.wa_token}
		message_api = self.get_api_url() + "/messages"
		frappe.enqueue(
			self.send_common_message, # python function or a module path as string
			queue="default", # one of short, default, long
			timeout=None, # pass timeout manually
			is_async=True, # if this is True, method is run in worker
			now=True, # if this is True, method is run directly (not in a worker)
			job_name="whatsapp_scheduled_message", # specify a job name
			enqueue_after_commit=False, # enqueue the job after the database commit is done at the end of the request
			# at_front=True, # put the job at the front of the queue
			whatsapp_api=message_api,
			message_template=message_template,
			headers=headers,
		)
		return True

@frappe.whitelist(allow_guest=True)
def update_whatsapp_status():
	rq = frappe.request
	print(rq.args)
	print("from update status")
	vt='mpqunelvoqkaugkdykfdjdfjkf'
	try:
		if 'hub.challenge' in rq.args:
			if rq.args['hub.verify_token'] == vt:
				from werkzeug.wrappers import Response
				return Response(rq.args['hub.challenge'])
			else:
				if frappe.request.method == "POST":
					rs = json.loads(frappe.request.data)
					print(rs)
					for en in rs['entry']:
						for ch in en['changes']:
							if 'statuses' in ch['value']:
								for status in ch['value']['statuses']:
									from datetime import datetime
									utime = datetime.fromtimestamp(float(status['timestamp']))
									wdoc = frappe.db.get_value("WhatsApp Settings", {'message_id':status['id']})

									if wdoc:
										wdoc = frappe.get_doc("WhatsApp Settings", wdoc)
										wdoc.status = status['status'].title()
										wdoc.save(
											ignore_permissions=True,
											ignore_version=True
										)
										frappe.db.commit()
										if wdoc.price_list_email_ref:
											if "PLE" in wdoc.price_list_email_ref and wdoc.msg_type == "price_list_email":
												frappe.db.sql("""update `tabPrice List Email` set msg_status=%s where name = %s""", (status['status'].title(), wdoc.price_list_email_ref), auto_commit=True)

								if 'messages' in  ch['value']:
									for msg in ch['value']['messages']:
										from datetime import datetime
										utime = datetime.fromtimestamp(int(msg['timestamp']))
										if msg['type']=="text":
											mdoc.message= msg['text']['body']
											mdoc= frappe.new_doc("Whatsapp Queue")
											mdoc.sales_invoice_ref= "customer_message"
											mdoc.msg_type= "customer_message"
											mdoc.recipient =  msg['from'].replace("91","",1)
											mdoc.status="received"
											mdoc.message_id = msg['id']
											mdoc.insert()
											frappe.db.commit()
				raise frappe.request
		return None
	except Exception as e:
		print("exceptions from updating status")
		print(e)
		return None




