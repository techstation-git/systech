import frappe
from frappe import _

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

def setup_custom_fields():
	# Placeholder for future custom fields
	pass
