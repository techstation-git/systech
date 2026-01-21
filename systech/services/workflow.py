import frappe
from frappe import _
from frappe.utils import flt

def before_workflow_action(doc, transition):
    """
    Hook to validate actions before they occur.
    """
    if doc.doctype == "Sales Order":
        # Check 1: Initial Submission (Draft -> Pending)
        # Prevent reservation if stock is insufficient.
        if transition.action == "Submit To Manager":
            validate_stock_availability(doc)
            pass

        # Check 2: Final Release (Locked -> Released)
        # Safety check (optional based on new flow, but good to keep)
        if transition.action == "Submit for Dispatch":
           pass # We can relax this or keep it. User focused on the first one. 
                # Let's keep the logic simple and focus on the first one as requested.

def validate_stock_availability(doc):
    """
    Check if we can reserve this stock.
    Condition: (Actual - Reserved) >= Required
    """
    problematic_items = []
    conflicting_orders_map = {} # item_code -> list of order names

    for item in doc.items:
        if not item.item_code or item.is_stock_item == 0:
            continue
            
        warehouse = item.warehouse
        if not warehouse:
            continue
            
        # Get Stock Info
        bin_data = frappe.db.get_value("Bin", 
            {"item_code": item.item_code, "warehouse": warehouse}, 
            ["actual_qty", "reserved_qty"], 
            as_dict=True
        )
        
        actual = flt(bin_data.actual_qty) if bin_data else 0.0
        reserved = flt(bin_data.reserved_qty) if bin_data else 0.0
        
        # Available for NEW reservation
        available = actual - reserved
        
        # Debug
        print(f"DEBUG: Stock Check (Draft) - Item: {item.item_code}, Warehouse: {warehouse}, Actual: {actual}, Reserved: {reserved}, Available: {available}, Required: {item.qty}")

        if available < item.qty:
            # SHORTAGE DETECTED
            problematic_items.append(f"<b>{item.item_code}</b> (Required: {item.qty}, Available: {available})")
            
            # Find Conflicting Locked Orders
            # These are orders acting as 'blockers' (Locked State)
            blockers = frappe.db.sql("""
                SELECT DISTINCT parent 
                FROM `tabSales Order Item`
                WHERE item_code = %s
                AND warehouse = %s
                AND docstatus = 1
                AND parent != %s
            """, (item.item_code, warehouse, doc.name), as_dict=True)
            
            # Filter for Locked state only (if requested, or just all submitted)
            # User said: "are in Locked(items reserved)"
            locked_blockers = []
            for b in blockers:
                 state = frappe.db.get_value("Sales Order", b.parent, "workflow_state")
                 if state == "Locked":
                     locked_blockers.append(b.parent)
            
            if locked_blockers:
                conflicting_orders_map[item.item_code] = locked_blockers

    if problematic_items:
        msg = _("<h5>Insufficient Stock to Submit</h5>")
        msg += _("You cannot submit this order because the following items do not have enough available stock:")
        msg += "<ul>" + "".join([f"<li>{s}</li>" for s in problematic_items]) + "</ul>"
        
        if conflicting_orders_map:
            msg += "<hr>"
            msg += _("<b>The stock is currently reserved by the following Locked Orders. Please request a release:</b><br>")
            
            for item_code, orders in conflicting_orders_map.items():
                msg += f"<p>Item: {item_code}</p>"
                for order in orders:
                    # Link to the order
                    msg += f'<a href="/app/sales-order/{order}" target="_blank" style="font-weight:bold; color:#ff5858;">{order}</a> &nbsp; '
        
        frappe.throw(msg, title=_("Stock Unavailable"))


@frappe.whitelist()
def request_release(docname, source_docname=None):
    """
    Notify Sales Manager to release stock from a Locked order.
    If source_docname is provided, set its state to 'Release Requested'.
    """
    if not docname:
        frappe.throw(_("Missing Document Name"))
        
    frappe.flags.ignore_permissions = True
    try:
        doc = frappe.get_doc("Sales Order", docname)
    finally:
        frappe.flags.ignore_permissions = False
    
    managers = [u.parent for u in frappe.get_all("Has Role", filters={"role": "Sales Manager", "parenttype": "User"}, fields=["parent"])]
    
    for manager in managers:
        notification = frappe.new_doc("Notification Log")
        notification.for_user = manager
        notification.type = "Alert"
        notification.subject = _("Stock Release Requested")
        notification.email_content = _("User {0} has requested to release stock from Locked Sales Order {1}. Reference Source Order: {2}").format(
            frappe.session.user, docname, source_docname or "N/A"
        )
        notification.document_type = "Sales Order"
        notification.document_name = docname
        notification.insert(ignore_permissions=True)
    
    # Update Workflow State -> Custom Field 'custom_release_status'
    # User removed 'Release Requested' from workflow states.
    if doc.custom_release_status != "Requested":
        # Using db_set to auto-commit and avoid full save overhead if possible, 
        # but doc.save() is safer for triggers. Since permissions are ignored, save() is fine.
        doc.custom_release_status = "Requested"
        doc.save(ignore_permissions=True)
        # frappe.db.set_value("Sales Order", docname, "custom_release_status", "Requested")
        
    # Update Source Order State (The one waiting)
    if source_docname:
        frappe.flags.ignore_permissions = True
        try:
            source_doc = frappe.get_doc("Sales Order", source_docname)
            if source_doc.custom_release_status != "Requested":
                source_doc.custom_release_status = "Requested"
                source_doc.save(ignore_permissions=True)
        finally:
            frappe.flags.ignore_permissions = False

    return "Notification Sent"

@frappe.whitelist()
def check_dependencies_on_release(doc, method=None):
    """
    Triggered when a Sales Order is Unreserved/Cancelled/Released.
    Checks if any 'Release Requested' orders can now be processed.
    """
    target_states = ["Closed", "Cancelled"] 
    # If doc is in these states, or docstatus is 2.
    
    if doc.status == "Closed" and doc.docstatus == 1:
        # Force update reserved qty to ensure it drops to 0.
        # Standard update_reserved_qty might not be enough if it re-reads docstatus=1.
        # We explicitly update the Bin to remove this order's reservation.
        doc.update_reserved_qty()
        
        # Aggressive Fix: Iterate items and ensure Bin is updated
        from erpnext.stock.utils import get_bin
        for d in doc.items:
            if d.item_code and d.warehouse:
                bin_obj = get_bin(d.item_code, d.warehouse)
                bin_obj.update_reserved_qty()
                
    if doc.workflow_state not in target_states and doc.docstatus != 2:
        return

    # Enqueue the check to ensure current transaction (Lock/Close) is committed 
    # and Bin is updated before we check stock for others.
    frappe.enqueue("systech.services.workflow.process_candidates", queue="default", timeout=300)

@frappe.whitelist()
def process_candidates():
    # Find candidate orders waiting for release
    candidates = frappe.get_all("Sales Order", 
        filters={"custom_release_status": "Requested", "docstatus": 0}, 
        fields=["name", "owner"]
    )
    
    if not candidates:
        return
        
    for candidate in candidates:
        # Check stock for this candidate
        res = check_stock_availability(candidate.name)
        
        if res.get("status") == "success":
            # Stock is now available!
            frappe.flags.ignore_permissions = True
            try:
                c_doc = frappe.get_doc("Sales Order", candidate.name)
                c_doc.workflow_state = "Pending Manager Approval"
                c_doc.custom_release_status = "" # Clear the request flag
                c_doc.save(ignore_permissions=True)
                
                # Notify Owner
                notification = frappe.new_doc("Notification Log")
                notification.for_user = candidate.owner
                notification.type = "Alert"
                notification.subject = _("Stock Available - Order Promoted")
                notification.email_content = _("Stock is now available for your Sales Order {0}. It has been moved to 'Pending Manager Approval'.").format(candidate.name)
                notification.document_type = "Sales Order"
                notification.document_name = candidate.name
                notification.insert(ignore_permissions=True)
            finally:
                frappe.flags.ignore_permissions = False

@frappe.whitelist()
def check_stock_availability(docname):
    """
    Check availability and return blockers if any.
    Returns:
    {
        "status": "success" | "failed",
        "items": [list of problematic items],
        "blockers": [list of locked orders]
    }
    """
    if not docname:
        return {"status": "failed", "message": "Missing Document Name"}

    doc = frappe.get_doc("Sales Order", docname)
    problematic_items = []
    # blockers is a dict keyed by item_code to list of order names, 
    # but for JSON response we might want a flat list or grouped data.
    # Let's return a list of unique blocking orders with details.
    
    unique_blockers = {} # name -> {name, customer, items: set()}

    for item in doc.items:
        if not item.item_code or item.is_stock_item == 0:
            continue
            
        warehouse = item.warehouse
        if not warehouse:
            continue
            
        # Get Stock Info
        bin_data = frappe.db.get_value("Bin", 
            {"item_code": item.item_code, "warehouse": warehouse}, 
            ["actual_qty", "reserved_qty"], 
            as_dict=True
        )
        
        actual = flt(bin_data.actual_qty) if bin_data else 0.0
        reserved = flt(bin_data.reserved_qty) if bin_data else 0.0
        
        # Available for NEW reservation
        available = actual - reserved
        
        if available < item.qty:
            # SHORTAGE DETECTED
            problematic_items.append({
                "item_code": item.item_code,
                "required": item.qty,
                "available": available,
                "actual": actual,
                "reserved": reserved,
                "shortage": item.qty - available
            })
            
            # Find Conflicting Locked Orders
            # These are orders acting as 'blockers' (Locked State)
            blockers = frappe.db.sql("""
                SELECT DISTINCT parent 
                FROM `tabSales Order Item`
                WHERE item_code = %s
                AND warehouse = %s
                AND docstatus = 1
                AND parent != %s
            """, (item.item_code, warehouse, doc.name), as_dict=True)
            
            for b in blockers:
                 # Check workflow state
                 details = frappe.db.get_value("Sales Order", b.parent, ["workflow_state", "customer", "owner", "custom_release_status", "status"], as_dict=True)
                 
                 # Explicit Closed Check in Python to be safe/verbose
                 if details.status == "Closed":
                     continue

                 if details and (details.workflow_state == "Locked" or details.workflow_state == "Approved"):
                     if b.parent not in unique_blockers:
                         # Get reserved Qty for this item in this order
                         # We can query 'Sales Order Item' for qty
                         item_qty = frappe.db.get_value("Sales Order Item", {"parent": b.parent, "item_code": item.item_code}, "qty")
                         
                         unique_blockers[b.parent] = {
                             "name": b.parent,
                             "customer": details.customer,
                             "owner": details.owner,
                             "qty": item_qty,
                             "custom_release_status": details.custom_release_status,
                             "items": []
                         }
                     unique_blockers[b.parent]["items"].append(item.item_code)



    # Convert items set to list for JSON serialization
    final_blockers = []
    for name, data in unique_blockers.items():
        data["items"] = list(data["items"])
        final_blockers.append(data)

    if problematic_items:
        return {
            "status": "failed",
            "items": problematic_items,
            "blockers": final_blockers
        }
    
    return {"status": "success"}

@frappe.whitelist()
def apply_fix():
    name = "Sales Order-status-allow_on_submit"
    if not frappe.db.exists("Property Setter", name):
        p = frappe.new_doc("Property Setter")
        p.name = name
        p.doctype_or_field = "DocField"
        p.doc_type = "Sales Order"
        p.field_name = "status"
        p.property = "allow_on_submit"
        p.property_type = "Check"
        p.value = "1"
        p.insert(ignore_permissions=True)
        print("Property Setter Created")
    else:
        frappe.db.set_value("Property Setter", name, "value", "1")
        print("Property Setter Updated")
    
    frappe.clear_cache(doctype="Sales Order")
    return "Fix Applied"
