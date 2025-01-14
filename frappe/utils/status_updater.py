import frappe
from frappe import _
from frappe.utils import flt, cint, nowdate, getdate
from frappe.model.document import Document


class OverAllowanceError(frappe.ValidationError):
	pass


class StatusUpdater(Document):
	def set_status(self, update=False, status=None, update_modified=True):
		if self.get('status_map'):
			previous_status = self.status
			if status:
				self.status = status
				if update:
					self.db_set("status", status, update_modified=update_modified)

			sl = self.status_map[:]
			sl.reverse()
			for s, condition in sl:
				if not condition:
					self.status = s
					break
				elif condition.startswith("eval:"):
					if frappe.safe_eval(condition[5:], None, {
						"self": self.as_dict(),
						"getdate": getdate,
						"nowdate": nowdate,
						"get_value": frappe.db.get_value
					}):
						self.status = s
						break
				elif getattr(self, condition)():
					self.status = s
					break

			self.add_status_comment(previous_status)

			if update:
				self.db_set('status', self.status, update_modified=update_modified)

	def add_status_comment(self, previous_status):
		if self.is_new():
			return

		if self.status != previous_status and self.status not in ("Cancelled", "Draft"):
			self.add_comment("Label", _(self.status))

	def get_completion_status(
		self,
		percentage_field,
		keyword,
		not_applicable=False,
		not_applicable_based_on=None,
		within_allowance=False
	):
		if self.docstatus == 2:
			return "Not Applicable"

		percentage = flt(self.get(percentage_field))
		rounded_percentage = flt(percentage, self.precision(percentage_field))

		not_applicable_percentage = flt(self.get(not_applicable_based_on or percentage_field))
		rounded_not_applicable_percentage = flt(not_applicable_percentage,
			self.precision(percentage_field))

		if not_applicable and rounded_not_applicable_percentage <= 0:
			return "Not Applicable"
		elif rounded_percentage >= 100 or within_allowance or not_applicable:
			suffix = "d" if keyword.endswith("e") else "ed"
			return f"{keyword}{suffix}"
		else:
			return f"To {keyword}"

	def calculate_status_percentage(
		self,
		completed_field,
		reference_field,
		items=None,
		under_delivery_allowance=False
	):
		if items is None:
			items = self.get('items', [])

		if items:
			precision = items[0].precision(reference_field)
		else:
			precision = cint(frappe.db.get_default("float_precision")) or 3

		# Allow both: single and multiple completed qty fieldnames
		if not isinstance(completed_field, list):
			completed_field = [completed_field]

		under_delivery_percentage = 0
		if under_delivery_allowance:
			under_delivery_percentage = flt(self.get_under_delivery_percentage())

		# Calculate Total Qty and Total Completed Qty
		total_reference_qty = 0
		total_completed_qty = 0
		within_allowance = True
		for row in items:
			completed_qty = 0
			for f in completed_field:
				completed_qty += abs(flt(row.get(f), precision))

			reference_qty = abs(flt(row.get(reference_field), precision))
			completed_qty = min(completed_qty, reference_qty)

			min_qty = flt(reference_qty - (reference_qty * under_delivery_percentage / 100), precision)
			if completed_qty < min_qty:
				within_allowance = False

			total_reference_qty += reference_qty
			total_completed_qty += completed_qty

		total_reference_qty = flt(total_reference_qty, precision)
		total_completed_qty = flt(total_completed_qty, precision)

		if total_reference_qty:
			completed_percentage = flt(total_completed_qty / total_reference_qty * 100, 3)
			if under_delivery_allowance:
				return completed_percentage, within_allowance
			else:
				return completed_percentage
		else:
			if under_delivery_allowance:
				return None, False
			else:
				return None

	def validate_completed_qty(
		self,
		completed_field,
		reference_field,
		items=None,
		allowance_type=None,
		max_qty_field=None,
		from_doctype=None,
		row_names=None,
		item_field="item_code"
	):
		items = self.get_rows_for_qty_validation(items, row_names)
		for row in items:
			self.validate_completed_qty_for_row(
				row,
				completed_field=completed_field,
				reference_field=reference_field,
				allowance_type=allowance_type,
				max_qty_field=max_qty_field,
				from_doctype=from_doctype,
				item_field=item_field,
			)

	def get_rows_for_qty_validation(self, items=None, row_names=None):
		if items is None:
			items = self.get('items', [])

		rows = []
		for row in items:
			if row_names is None or row.name in row_names:
				rows.append(row)

		return rows

	def validate_completed_qty_for_row(
		self,
		row,
		completed_field,
		reference_field,
		allowance_type=None,
		max_qty_field=None,
		from_doctype=None,
		item_field="item_code"
	):
		# Allow both: single and multiple completed qty fieldnames
		if not isinstance(completed_field, list):
			completed_field = [completed_field]

		reference_qty = flt(row.get(reference_field), row.precision(reference_field))

		completed_qty = sum([flt(row.get(f)) for f in completed_field])
		completed_qty = flt(completed_qty, row.precision(reference_field))

		if not allowance_type:
			difference = completed_qty - reference_qty
			excess_qty = difference
		elif allowance_type == "max_qty_field":
			max_qty = flt(row.get(max_qty_field), row.precision(reference_field))
			excess_qty = completed_qty - max_qty
		else:
			excess_qty = self.get_excess_qty_with_allowance(row, completed_field, reference_field, allowance_type,
				item_field=item_field)

		if reference_qty < 0:
			excess_qty = -1 * excess_qty

		rounded_excess = flt(excess_qty, row.precision(reference_field))

		if rounded_excess > 0:
			self.limits_crossed_error(row, completed_field, reference_field, allowance_type, excess_qty,
				from_doctype=from_doctype, item_field=item_field)

	def limits_crossed_error(self,
		row,
		completed_field,
		reference_field,
		allowance_type,
		excess_qty=None,
		from_doctype=None,
		item_field="item_code"
	):
		"""Raise exception for limits crossed"""
		reference_qty = flt(row.get(reference_field))

		# Allow both: single and multiple completed qty fieldnames
		if not isinstance(completed_field, list):
			completed_field = [completed_field]

		completed_qty = 0
		for f in completed_field:
			completed_qty += flt(row.get(f))

		if excess_qty is None:
			excess_qty = completed_qty - reference_qty

		formatted_reference_qty = row.get_formatted(reference_field)
		formatted_completed_qty = frappe.format(completed_qty, df=row.meta.get_field(completed_field[0]), doc=row)
		formatted_excess = frappe.format(excess_qty, df=row.meta.get_field(reference_field), doc=row)

		reference_field_label = row.meta.get_label(reference_field)

		completed_field_label = []
		for f in completed_field:
			completed_field_label.append(row.meta.get_label(f))
		completed_field_label = " + ".join(completed_field_label)

		over_limit_msg = _("{0} for Item {1} is over limit by {2}.").format(
			frappe.bold(completed_field_label),
			frappe.bold(row.get(item_field) or row.get('item_name')),
			frappe.bold(formatted_excess)
		)

		actual_qty_msg = _("{0} {1} is {2}, however, {3} is {4}").format(
			frappe.bold(self.doctype),
			frappe.bold(reference_field_label),
			frappe.bold(formatted_reference_qty),
			frappe.bold(completed_field_label),
			frappe.bold(formatted_completed_qty),
		)

		from_doctype_msg = ""
		if from_doctype:
			from_doctype_msg = _("Are you making a duplicate {0} against the same {1}?").format(
				frappe.bold(from_doctype),
				frappe.bold(self.doctype),
			)

		suggestion_msg = self.get_overallowance_error_suggestion_message(allowance_type)

		full_msg = over_limit_msg + "<br>" + actual_qty_msg

		if from_doctype_msg:
			full_msg += "<br><br>" + from_doctype_msg
		if suggestion_msg:
			full_msg += "<br><br>" + suggestion_msg

		frappe.throw(full_msg, OverAllowanceError, title=_('{0} Limit Crossed').format(completed_field_label))

	def get_excess_qty_with_allowance(
		self,
		row,
		completed_field,
		reference_field,
		allowance_type,
		item_field="item_code"
	):
		"""
			Checks if there is overflow condering a relaxation allowance
		"""
		reference_qty = flt(row.get(reference_field))
		if not reference_qty:
			return 0

		# Allow both: single and multiple completed qty fieldnames
		if not isinstance(completed_field, list):
			completed_field = [completed_field]

		completed_qty = 0
		for f in completed_field:
			completed_qty += flt(row.get(f))

		difference = completed_qty - reference_qty

		# check if overflow is within allowance
		allowance = self.get_allowance_for(allowance_type, item_code=row.get(item_field))
		overflow_percent = difference / reference_qty * 100

		excess_qty = 0
		if overflow_percent - allowance > 0.01:
			max_allowed = flt(reference_qty * (100 + allowance) / 100)
			excess_qty = completed_qty - max_allowed

		return excess_qty

	def get_under_delivery_percentage(self):
		return 0

	def get_allowance_for(self, allowance_type, item_code=None):
		return 0

	def get_overallowance_error_suggestion_message(self, allowance_type):
		return ""
