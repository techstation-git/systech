# Copyright (c) 2024, Systech and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data

def get_columns():
	return [
		{
			"label": _("Date"),
			"fieldname": "posting_date",
			"fieldtype": "Date",
			"width": 100
		},
		{
			"label": _("Time"),
			"fieldname": "posting_time",
			"fieldtype": "Time",
			"width": 100
		},
		{
			"label": _("Item Code"),
			"fieldname": "item_code",
			"fieldtype": "Link",
			"options": "Item",
			"width": 120
		},
		{
			"label": _("Item Name"),
			"fieldname": "item_name",
			"fieldtype": "Data",
			"width": 150
		},
		{
			"label": _("Warehouse"),
			"fieldname": "warehouse",
			"fieldtype": "Link",
			"options": "Warehouse",
			"width": 120
		},
		{
			"label": _("Qty Change"),
			"fieldname": "actual_qty",
			"fieldtype": "Float",
			"width": 100,
			"convertible": "qty"
		},
		{
			"label": _("Voucher Type"),
			"fieldname": "voucher_type",
			"fieldtype": "Data",
			"width": 140
		},
		{
			"label": _("Voucher No"),
			"fieldname": "voucher_no",
			"fieldtype": "Dynamic Link",
			"options": "voucher_type",
			"width": 140
		}
	]

def get_data(filters):
	conditions = ""
	
	if filters.get("company"):
		conditions += f" AND company = '{filters.get('company')}'"

	if filters.get("warehouse"):
		conditions += f" AND warehouse = '{filters.get('warehouse')}'"
	
	if filters.get("item_code"):
		conditions += f" AND item_code = '{filters.get('item_code')}'"

	if filters.get("from_date"):
		conditions += f" AND posting_date >= '{filters.get('from_date')}'"

	if filters.get("to_date"):
		conditions += f" AND posting_date <= '{filters.get('to_date')}'"

	sql = f"""
		SELECT
			sle.posting_date,
			sle.posting_time,
			sle.item_code,
			item.item_name,
			sle.warehouse,
			sle.actual_qty,
			sle.voucher_type,
			sle.voucher_no
		FROM
			`tabStock Ledger Entry` sle
		LEFT JOIN
			`tabItem` item ON sle.item_code = item.name
		WHERE
			sle.docstatus = 1
			{conditions}
		ORDER BY
			sle.posting_date DESC, sle.posting_time DESC
	"""
	
	data = frappe.db.sql(sql, as_dict=True)
	return data
