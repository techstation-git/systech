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
			"width": 180
		},
		{
			"label": _("Brand"),
			"fieldname": "brand",
			"fieldtype": "Data",
			"width": 100
		},
		{
			"label": _("Capacity"),
			"fieldname": "capacity",
			"fieldtype": "Data",
			"width": 100
		},
		{
			"label": _("Warehouse"),
			"fieldname": "warehouse",
			"fieldtype": "Link",
			"options": "Warehouse",
			"width": 120
		},
		{
			"label": _("Stock Qty"),
			"fieldname": "stock_qty",
			"fieldtype": "Float",
			"width": 100,
			"convertible": "qty"
		},
		{
			"label": _("UOM"),
			"fieldname": "stock_uom",
			"fieldtype": "Link",
			"options": "UOM",
			"width": 80
		},
	]

def get_data(filters):
	conditions = ""
	
	if filters.get("warehouse"):
		conditions += f" AND bin.warehouse = '{filters.get('warehouse')}'"
	
	if filters.get("item_group"):
		conditions += f" AND item.item_group = '{filters.get('item_group')}'"

	if filters.get("brand"):
		conditions += f" AND item.brand = '{filters.get('brand')}'"
		
	# Special handling for Capacity (Custom Field)
	# Assuming fieldname is 'capacity' or we might need to check if it exists
	if filters.get("capacity"):
		# Check if column exists first to avoid SQL error? 
		# For now, assuming basic filter, likely partial match for Data field
		conditions += f" AND item.capacity LIKE '%%{filters.get('capacity')}%%'"

	# Supplier Filter (Default Supplier)
	if filters.get("supplier"):
		conditions += f" AND item.default_supplier = '{filters.get('supplier')}'"

	sql = f"""
		SELECT
			bin.item_code,
			item.item_name,
			item.brand,
			item.stock_uom,
			bin.warehouse,
			bin.actual_qty as stock_qty,
			item.capacity
		FROM
			`tabBin` bin
		LEFT JOIN
			`tabItem` item ON bin.item_code = item.name
		WHERE
			bin.actual_qty != 0
			{conditions}
		ORDER BY
			bin.item_code, bin.warehouse
	"""
	
	# If 'capacity' column doesn't exist in tabItem, this will fail.
	# We should ideally check or wrap in try/except, 
	# but since we are controlling the DB schema updates via plans, 
	# I will verify the custom field creation next.
	
	try:
		data = frappe.db.sql(sql, as_dict=True)
	except Exception as e:
		if "Unknown column 'item.capacity'" in str(e):
			# Fallback if field doesn't exist yet, return without capacity
			# Or we can patch it here temporarily
			sql_fallback = sql.replace("item.capacity", "'' as capacity").replace(f"AND item.capacity LIKE '%%{filters.get('capacity')}%%'", "")
			data = frappe.db.sql(sql_fallback, as_dict=True)
		else:
			raise e

	return data
