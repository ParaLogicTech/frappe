import frappe

MESSAGE_PLACEHOLDER = "Add your message here"


def execute():
	# System Notification rules now take their bell text from Notification Title and Notification Message,
	# and the form hides Subject and Message for that channel. Copy the old values over so existing rules
	# show them when edited, instead of an empty, mandatory title.
	notification = frappe.qb.DocType("Notification")
	is_system_notification = notification.channel == "System Notification"

	def is_empty(column):
		return column.isnull() | (column == "")

	(
		frappe.qb.update(notification)
		.set(notification.notification_title, notification.subject)
		.where(
			is_system_notification
			& is_empty(notification.notification_title)
			& ~is_empty(notification.subject)
		)
	).run()

	(
		frappe.qb.update(notification)
		.set(notification.notification_message, notification.message)
		.where(
			is_system_notification
			& is_empty(notification.notification_message)
			& ~is_empty(notification.message)
			& (notification.message != MESSAGE_PLACEHOLDER)
		)
	).run()
