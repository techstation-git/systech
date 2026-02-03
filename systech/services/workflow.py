import frappe
from frappe import _
from frappe.utils import flt

def before_workflow_action(doc, transition):
    """
    Hook to validate actions before they occur.
    """
    if doc.doctype == "Sales Order":
        # Check 1: Initial Submission (Draft -> Pending)
        # DISABLED: Stock validation moved to Delivery Note creation (standard ERPNext behavior)
        # if transition.action == "Submit To Manager":
        #     validate_stock_availability(doc)
        pass  # Stock is now reserved when Delivery Note is created, not on SO approval
            
        if transition.action == "Approve":
            total_remaining = sum([flt(d.qty) for d in doc.items])
            if total_remaining <= 0:
                doc.status = "Cancelled"
                doc.workflow_state = "Cancelled"
                doc.db_set("status", "Cancelled")
                doc.db_set("workflow_state", "Cancelled")

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
                 if state == "Approved":
                     locked_blockers.append(b.parent)
            
            if locked_blockers:
                conflicting_orders_map[item.item_code] = locked_blockers

    if problematic_items:
        msg = _("<h5>Insufficient Stock to Submit</h5>")
        msg += _("You cannot submit this order because the following items do not have enough available stock:")
        msg += "<ul>" + "".join([f"<li>{s}</li>" for s in problematic_items]) + "</ul>"
        
        if conflicting_orders_map:
            msg += "<hr>"
            msg += _("<b>The stock is currently reserved by the following Approved Orders. Please request a release:</b><br>")
            
            for item_code, orders in conflicting_orders_map.items():
                msg += f"<p>Item: {item_code}</p>"
                for order in orders:
                    # Link to the order
                    msg += f'<a href="/app/sales-order/{order}" target="_blank" style="font-weight:bold; color:#ff5858;">{order}</a> &nbsp; '
        
        frappe.throw(msg, title=_("Stock Unavailable"))


@frappe.whitelist()
def request_release(docname, source_docname=None):
    """
    Notify Sales Manager to release stock from an Approved order.
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
    manager_emails = [frappe.db.get_value("User", m, "email") for m in managers]
    manager_emails = [e for e in manager_emails if e]
    
    subject = _("Stock Release Requested: {0}").format(docname)
    content = _("User {0} has requested to release stock from Approved Sales Order {1}. Reference Source Order: {2}").format(
        frappe.session.user, docname, source_docname or "N/A"
    )

    for manager in managers:
        notification = frappe.new_doc("Notification Log")
        notification.for_user = manager
        notification.type = "Alert"
        notification.subject = subject
        notification.email_content = content
        notification.document_type = "Sales Order"
        notification.document_name = docname
        notification.insert(ignore_permissions=True)
    
    if manager_emails:
        frappe.sendmail(
            recipients=manager_emails,
            subject=subject,
            message=content,
            reference_doctype="Sales Order",
            reference_name=docname
        )
    
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
    Triggered when a Sales Order is Unreserved/Cancelled/Released/Updated.
    Checks if any 'Release Requested' orders can now be processed.
    """
    if doc.status == "Closed" and doc.docstatus == 1:
        # Force update reserved qty to ensure it drops to 0 immediately if Closed.
        doc.update_reserved_qty()
        
        from erpnext.stock.utils import get_bin
        for d in doc.items:
            if d.item_code and d.warehouse:
                bin_obj = get_bin(d.item_code, d.warehouse)
                bin_obj.update_reserved_stock()
                
    # We trigger process_candidates on EVERY update of a submitted SO 
    # to catch partial releases or state changes.
    if doc.docstatus == 1 or doc.docstatus == 2:
        frappe.enqueue("systech.services.workflow.process_candidates", queue="default", timeout=300)

@frappe.whitelist()
def process_candidates():
    # Find candidate orders waiting for release
    candidates = frappe.get_all("Sales Order", 
        filters={"custom_release_status": "Requested", "docstatus": 0}, 
        fields=["name", "owner"]
    )
    
    frappe.logger().debug(f"[Systech Workflow] Processing {len(candidates)} candidates for stock promotion")
    
    if not candidates:
        return
        
    for candidate in candidates:
        # Check stock for this candidate
        res = check_stock_availability(candidate.name)
        
        frappe.logger().debug(f"[Systech Workflow] Candidate {candidate.name} check result: {res.get('status')}")
        
        if res.get("status") == "success":
            # Stock is now available!
            frappe.flags.ignore_permissions = True
            try:
                c_doc = frappe.get_doc("Sales Order", candidate.name)
                
                if c_doc.custom_release_status != "Requested":
                    continue

                frappe.logger().info(f"[Systech Workflow] Promoting {candidate.name} to Pending Manager Approval")
                
                c_doc.workflow_state = "Pending Manager Approval"
                c_doc.custom_release_status = "" # Clear the request flag
                c_doc.flags.ignore_validate_update_after_submit = True
                c_doc.save(ignore_permissions=True)
                
                # Notify Owner
                subject = _("Stock Available - Order Promoted: {0}").format(candidate.name)
                content = _("Stock is now available for your Sales Order {0}. It has been moved to 'Pending Manager Approval'.").format(candidate.name)

                notification = frappe.new_doc("Notification Log")
                notification.for_user = candidate.owner
                notification.type = "Alert"
                notification.subject = subject
                notification.email_content = content
                notification.document_name = candidate.name
                notification.document_type = "Sales Order"
                notification.insert(ignore_permissions=True)
                
                owner_email = frappe.db.get_value("User", candidate.owner, "email")
                if owner_email:
                    frappe.sendmail(
                        recipients=[owner_email],
                        subject=subject,
                        message=content,
                        reference_doctype="Sales Order",
                        reference_name=candidate.name
                    )
                
                frappe.db.commit()
            except Exception as e:
                frappe.logger().error(f"[Systech Workflow] Failed to promote {candidate.name}: {str(e)}")
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
        "blockers": [list of approved orders]
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

                 if details and details.workflow_state == "Approved":
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

    # Qty in Sales Order Item
    qty_name = "Sales Order Item-qty-allow_on_submit"
    if not frappe.db.exists("Property Setter", qty_name):
        p = frappe.new_doc("Property Setter")
        p.name = qty_name
        p.doctype_or_field = "DocField"
        p.doc_type = "Sales Order Item"
        p.field_name = "qty"
        p.property = "allow_on_submit"
        p.property_type = "Check"
        p.value = "1"
        p.insert(ignore_permissions=True)
    
    # Items table in Sales Order
    items_name = "Sales Order-items-allow_on_submit"
    if not frappe.db.exists("Property Setter", items_name):
        p = frappe.new_doc("Property Setter")
        p.name = items_name
        p.doctype_or_field = "DocField"
        p.doc_type = "Sales Order"
        p.field_name = "items"
        p.property = "allow_on_submit"
        p.property_type = "Check"
        p.value = "1"
        p.insert(ignore_permissions=True)
    
    frappe.clear_cache(doctype="Sales Order")
    frappe.clear_cache(doctype="Sales Order Item")
    return "Fix Applied"

@frappe.whitelist()
def release_stock_manually(docname, item_releases):
    """
    Manually release stock from an Approved Sales Order.
    item_releases: JSON string or dict mapping item name (row ID) to qty_to_release
    """
    import json
    if isinstance(item_releases, str):
        item_releases = json.loads(item_releases)
        
    doc = frappe.get_doc("Sales Order", docname)
    total_remaining = 0.0
    
    # Track items partially released for notification
    released_items = []

    for item in doc.items:
        rel_qty = flt(item_releases.get(item.name, 0.0))
        if rel_qty > 0:
            if rel_qty > item.qty:
                frappe.throw(_("Cannot release more than current quantity for item {0}").format(item.item_code))
            
            item.qty = item.qty - rel_qty
            released_items.append({"item_code": item.item_code, "qty": rel_qty})
            
        total_remaining += item.qty
        
    if total_remaining <= 0:
        doc.status = "Cancelled"
        doc.workflow_state = "Cancelled"
    
    # We also clear release request status if it was set
    doc.custom_release_status = ""
    
    doc.flags.ignore_validate_update_after_submit = True
    doc.save(ignore_permissions=True)
    
    # Force update reserved qty for all items
    doc.update_reserved_qty()
    
    # Aggressively ensure Bin reflects the change
    from erpnext.stock.utils import get_bin
    for d in doc.items:
        if d.item_code and d.warehouse:
            bin_obj = get_bin(d.item_code, d.warehouse)
            bin_obj.update_reserved_stock()
            
    if total_remaining <= 0:
        # Using db_set to bypass any ERPNext status reset logic
        doc.db_set("status", "Cancelled")
        doc.db_set("workflow_state", "Cancelled")

    # Explicit Notification for those who requested release
    if released_items:
        # Find all candidates currently waiting for stock.
        candidates = frappe.get_all("Sales Order", 
            filters={"custom_release_status": "Requested", "docstatus": 0}, 
            fields=["name", "owner"]
        )
        
        item_list_str = ", ".join([f"{r['qty']} of {r['item_code']}" for r in released_items])
        
        for candidate in candidates:
            # Re-verify stock for this specific candidate synchronously? 
            # No, process_candidates is enqueued by doc.save() trigger anyway.
            # But let's send a preliminary notification.
            subject = _("Stock Released (Partial): {0}").format(docname)
            content = _("Stock ({0}) has been released from Approved Order {1}. Your Sales Order {2} is being re-evaluated.").format(
                item_list_str, docname, candidate.name
            )

            notification = frappe.new_doc("Notification Log")
            notification.for_user = candidate.owner
            notification.type = "Alert"
            notification.subject = subject
            notification.email_content = content
            notification.document_name = candidate.name
            notification.document_type = "Sales Order"
            notification.insert(ignore_permissions=True)
            
            owner_email = frappe.db.get_value("User", candidate.owner, "email")
            if owner_email:
                frappe.sendmail(
                    recipients=[owner_email],
                    subject=subject,
                    message=content,
                    reference_doctype="Sales Order",
                    reference_name=candidate.name
                )
            
    return {"status": "success", "closed": total_remaining <= 0}
