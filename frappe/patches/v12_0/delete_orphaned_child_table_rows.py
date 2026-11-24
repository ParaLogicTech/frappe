import frappe


def execute():
	table_dts = frappe.db.sql_list("select name from `tabDocType` where istable = 1")
	for dt in table_dts:
		parents = frappe.db.sql("select distinct parenttype, parentfield from `tab{0}`".format(dt))
		if not parents:
			continue

		for parenttype, parentfield in parents:
			if not frappe.db.exists("DocType", parenttype):
				continue

			if not frappe.get_meta(parenttype).has_field(parentfield):
				continue

			if frappe.get_meta(parenttype).issingle:
				continue

			non_existent_parents = frappe.db.sql(
				"""
				select ch.name, ch.parent
				from `tab{dt}` ch
				left join `tab{parenttype}` p on p.name = ch.parent
				where p.name is null and ch.parenttype = '{parenttype}' and ch.parentfield = '{parentfield}'
			""".format(dt=dt, parenttype=parenttype, parentfield=parentfield),
				as_dict=1,
			)

			name_list = [d.name for d in non_existent_parents if d.name]
			parent_list = list(set([d.parent for d in non_existent_parents]))

			if name_list:
				print(
					"({0}, {1}, {2}) has {3} non existent parents".format(
						parenttype, dt, parentfield, len(parent_list)
					)
				)

				frappe.db.sql("delete from `tab{0}` where name in %s".format(dt), [name_list])
