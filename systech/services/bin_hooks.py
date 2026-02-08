import frappe
from frappe.utils import flt

def recalculate_bin_reserved_stock(doc, method=None):
    """
    Hook to recalculate Bin's reserved stock using smart logic after any update.
    Only counts reservations from:
    - Recent sales orders (last 3 months), OR
    - Older sales orders that have delivery notes
    """
    if not doc.item_code or not doc.warehouse:
        return
    
    # Calculate smart reserved qty
    reserved_data = frappe.db.sql("""
        SELECT SUM(so_item.qty - so_item.delivered_qty) as reserved_qty
        FROM `tabSales Order` so
        INNER JOIN `tabSales Order Item` so_item ON so_item.parent = so.name
        WHERE so_item.item_code = %(item_code)s
        AND so_item.warehouse = %(warehouse)s
        AND so.docstatus = 1
        AND so.status NOT IN ('Closed', 'Cancelled')
        AND so_item.qty > so_item.delivered_qty
        AND (
            -- Recent orders (last 3 months) always count
            so.transaction_date >= DATE_SUB(CURDATE(), INTERVAL 3 MONTH)
            OR
            -- Older orders only count if they have delivery notes
            EXISTS (
                SELECT 1 
                FROM `tabDelivery Note Item` dni
                WHERE dni.against_sales_order = so.name
                AND dni.docstatus = 1
            )
        )
    """, {
        "item_code": doc.item_code,
        "warehouse": doc.warehouse
    }, as_dict=True)
    
    smart_reserved_qty = flt(reserved_data[0].reserved_qty) if reserved_data and reserved_data[0].reserved_qty else 0.0
    
    # Only update if different to avoid infinite loops
    if flt(doc.reserved_qty) != smart_reserved_qty:
        doc.reserved_qty = smart_reserved_qty
        doc.set_projected_qty()
