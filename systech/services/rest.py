import frappe
from frappe import _
from frappe.model.workflow import apply_workflow

def validate_item_barcode(doc, method):
	"""
	Enforce that every Item must have at least one barcode.
	"""
	if not doc.barcodes:
		frappe.throw(_("Barcode is mandatory for Item: {0}").format(doc.name))

def validate_transaction_barcodes(doc, method):
	"""
	Enforce that all items in Purchase Receipt and Stock Entry have barcodes.
	"""
	for item in doc.items:
		# Check if the Item itself has barcodes (by fetching Item master)
		# Or checks if the transaction line has a barcode (if that's the requirement, 
		# but usually we check if the Item *has* a barcode in the system so scanning helps).
		# The requirement says: "Enforce mandatory barcode entry ... so that receiving ... are done via barcode scanning."
		# This usually means we want to ensure the Item being transacted HAS a barcode.
		
		# Let's verify if the Item has a barcode in the system.
		if not frappe.db.exists("Item Barcode", {"parent": item.item_code}):
			frappe.throw(_("Item {0} at Row {1} does not have a barcode in the system. Please add a barcode to the Item first.").format(item.item_code, item.idx))

@frappe.whitelist()
def check_if_warehouse_keeper():
	"""
	Returns True if the current user has the 'Warehouse Keeper' role.
	"""
	return frappe.user.has_role("Warehouse Keeper")

def apply_warehouse_security():
	"""
	Applies Property Setters to hide sensitive fields for 'Warehouse Keeper'.
	"""
	# Ensure Role Exists (Just in case, though user said it exists)
	if not frappe.db.exists("Role", "Warehouse Keeper"):
		frappe.get_doc({"doctype": "Role", "role_name": "Warehouse Keeper"}).insert(ignore_permissions=True)

	# Fields to hide
	# Structure: (DocType, FieldName, Property, Value)
	# For Grid fields, we need to target the Child Table DocType.
	
	definitions = [
		# Item
		("Item", "valuation_rate", "depends_on", 'eval:!frappe.user.has_role("Warehouse Keeper")'),
		("Item", "standard_rate", "depends_on", 'eval:!frappe.user.has_role("Warehouse Keeper")'),
		("Item", "last_purchase_rate", "depends_on", 'eval:!frappe.user.has_role("Warehouse Keeper")'),
		
		# Stock Entry
		("Stock Entry", "total_amount", "depends_on", 'eval:!frappe.user.has_role("Warehouse Keeper")'),
		("Stock Entry", "total_additional_costs", "depends_on", 'eval:!frappe.user.has_role("Warehouse Keeper")'),
		
		# Stock Entry Detail (Child Table)
		("Stock Entry Detail", "basic_rate", "depends_on", 'eval:!frappe.user.has_role("Warehouse Keeper")'),
		("Stock Entry Detail", "basic_amount", "depends_on", 'eval:!frappe.user.has_role("Warehouse Keeper")'),
		("Stock Entry Detail", "amount", "depends_on", 'eval:!frappe.user.has_role("Warehouse Keeper")'),
		("Stock Entry Detail", "valuation_rate", "depends_on", 'eval:!frappe.user.has_role("Warehouse Keeper")'),
		("Stock Entry Detail", "additional_cost", "depends_on", 'eval:!frappe.user.has_role("Warehouse Keeper")'),

		# Purchase Receipt
		("Purchase Receipt", "base_discount_amount", "depends_on", 'eval:!frappe.user.has_role("Warehouse Keeper")'),
		("Purchase Receipt", "base_grand_total", "depends_on", 'eval:!frappe.user.has_role("Warehouse Keeper")'),
		("Purchase Receipt", "base_net_total", "depends_on", 'eval:!frappe.user.has_role("Warehouse Keeper")'),
		("Purchase Receipt", "base_total", "depends_on", 'eval:!frappe.user.has_role("Warehouse Keeper")'),
		("Purchase Receipt", "base_total_taxes_and_charges", "depends_on", 'eval:!frappe.user.has_role("Warehouse Keeper")'),
		("Purchase Receipt", "discount_amount", "depends_on", 'eval:!frappe.user.has_role("Warehouse Keeper")'),
		("Purchase Receipt", "grand_total", "depends_on", 'eval:!frappe.user.has_role("Warehouse Keeper")'),
		("Purchase Receipt", "net_total", "depends_on", 'eval:!frappe.user.has_role("Warehouse Keeper")'),
		("Purchase Receipt", "total", "depends_on", 'eval:!frappe.user.has_role("Warehouse Keeper")'),
		("Purchase Receipt", "total_taxes_and_charges", "depends_on", 'eval:!frappe.user.has_role("Warehouse Keeper")'),
		("Purchase Receipt", "taxes", "depends_on", 'eval:!frappe.user.has_role("Warehouse Keeper")'), # Table field itself

		# Purchase Receipt Item (Child Table)
		("Purchase Receipt Item", "rate", "depends_on", 'eval:!frappe.user.has_role("Warehouse Keeper")'),
		("Purchase Receipt Item", "amount", "depends_on", 'eval:!frappe.user.has_role("Warehouse Keeper")'),
		("Purchase Receipt Item", "base_rate", "depends_on", 'eval:!frappe.user.has_role("Warehouse Keeper")'),
		("Purchase Receipt Item", "base_amount", "depends_on", 'eval:!frappe.user.has_role("Warehouse Keeper")'),
		("Purchase Receipt Item", "net_rate", "depends_on", 'eval:!frappe.user.has_role("Warehouse Keeper")'),
		("Purchase Receipt Item", "net_amount", "depends_on", 'eval:!frappe.user.has_role("Warehouse Keeper")'),
		("Purchase Receipt Item", "valuation_rate", "depends_on", 'eval:!frappe.user.has_role("Warehouse Keeper")'),
		("Purchase Receipt Item", "price_list_rate", "depends_on", 'eval:!frappe.user.has_role("Warehouse Keeper")'),
		("Purchase Receipt Item", "discount_amount", "depends_on", 'eval:!frappe.user.has_role("Warehouse Keeper")'),
		("Purchase Receipt Item", "discount_percentage", "depends_on", 'eval:!frappe.user.has_role("Warehouse Keeper")'),
	]

	for doctype, fieldname, property_name, value in definitions:
		# Check if Property Setter exists
		filters = {
			"doc_type": doctype,
			"field_name": fieldname,
			"property": property_name
		}
		if not frappe.db.exists("Property Setter", filters):
			frappe.make_property_setter({
				"doctype": doctype,
				"doctype_or_field": "DocField",
				"fieldname": fieldname,
				"property": property_name,
				"value": value,
				"is_system_generated": 0
			})
		else:
			# Update existing
			ps = frappe.get_doc("Property Setter", filters)
			ps.value = value
			ps.save()
	
	frappe.db.commit()

@frappe.whitelist()
def unreserve_stock(sales_order_name):
	"""
	Closes the Sales Order to unreserve stock.
	Only allowed for Sales Managers when the SO is Locked.
	"""
	if "Sales Manager" not in frappe.get_roles():
		frappe.throw(_("Only Sales Managers can perform this action."))

	doc = frappe.get_doc("Sales Order", sales_order_name)

	if doc.workflow_state != "Locked":
		frappe.throw(_("Sales Order must be in 'Locked' state to unreserve stock."))
	
	if doc.status == "Closed":
		frappe.msgprint(_("Sales Order is already closed."))
		return

	# Closing the Sales Order unreserves the stock
	doc.db_set("workflow_state", "Unreserved and Closed")
	doc.update_status("Closed")
	
	frappe.msgprint(_("Sales Order {0} has been closed and stock unreserved.").format(sales_order_name))

@frappe.whitelist()
def process_workflow_action(docname, action):
	"""
	Applies a workflow action to a Sales Order.
	"""
	if "Sales Manager" not in frappe.get_roles():
		frappe.throw(_("Only Sales Managers can perform this action."))

	doc = frappe.get_doc("Sales Order", docname)
	apply_workflow(doc, action)
	doc.save()
	
	frappe.msgprint(_("Sales Order {0}: {1} applied successfully.").format(docname, action))
	return doc.workflow_state

@frappe.whitelist()
def get_dashboard_stats():
	"""
	Returns counts for dashboard cards.
	"""
	if "Sales Manager" not in frappe.get_roles():
		return {}

	data = {}
	
	# Release Requested
	data['release'] = frappe.db.count('Sales Order', filters={'workflow_state': 'Release Requested', 'docstatus': 1})
	
	# Pending Approval
	data['approval'] = frappe.db.count('Sales Order', filters={'workflow_state': 'Pending Manager Approval'})
	
	# Locked (and qty)
	locked_stats = frappe.db.sql("""
		SELECT count(name) as count, sum(total_qty) as total_qty 
		FROM `tabSales Order` 
		WHERE workflow_state = 'Locked' AND docstatus = 1 AND status != 'Closed'
	""", as_dict=True)[0]
	
	data['locked_count'] = locked_stats.count or 0
	data['locked_qty'] = locked_stats.total_qty or 0
	
	return data


@frappe.whitelist()
def get_stock_release_list(workflow_state, status=None):
	"""
	Get list of Sales Orders for Stock Release Console.
	Fetches sales_person via subquery.
	"""
	if "Sales Manager" not in frappe.get_roles():
		return []

	conditions = ["workflow_state = %(workflow_state)s", "docstatus != 2"] # Exclude cancelled
	values = {"workflow_state": workflow_state}

	# Custom handling for the filter logic passed from JS
	if workflow_state == 'Locked':
		conditions.append("status != 'Closed'")
		conditions.append("docstatus = 1") # Locked must be submitted

	where_clause = " AND ".join(conditions)

	sql = f"""
		SELECT 
			name, 
			customer, 
			transaction_date, 
			grand_total, 
			currency, 
			total_qty,
			(SELECT sales_person FROM `tabSales Team` WHERE parent = `tabSales Order`.name LIMIT 1) as sales_person
		FROM `tabSales Order`
		WHERE {where_clause}
		ORDER BY transaction_date ASC
	"""

	return frappe.db.sql(sql, values, as_dict=True)





