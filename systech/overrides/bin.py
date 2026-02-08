import frappe
from frappe.utils import flt
from erpnext.stock.doctype.bin.bin import Bin

class CustomBin(Bin):
    """
    Custom Bin to use smart reserved stock calculation.
    Only counts reservations from recent orders or orders with delivery notes.
    """
    
    def update_reserved_stock(self, item_code=None, warehouse=None):
        """
        Override to use smart reservation calculation.
        Only counts:
        - Recent sales orders (last 3 months), OR
        - Older sales orders that have delivery notes
        
        This prevents old stuck orders from blocking inventory.
        """
        if not item_code:
            item_code = self.item_code
        if not warehouse:
            warehouse = self.warehouse
        
        # Use our smart reservation query
        reserved_qty = self._calculate_smart_reserved_qty(item_code, warehouse)
        
        # Update the bin
        self.db_set("reserved_qty", flt(reserved_qty))
        self.set_projected_qty()
    
    def _calculate_smart_reserved_qty(self, item_code, warehouse):
        """
        Calculate reserved qty using smart logic.
        Only counts recent orders or orders with delivery notes.
        """
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
            "item_code": item_code,
            "warehouse": warehouse
        }, as_dict=True)
        
        return flt(reserved_data[0].reserved_qty) if reserved_data and reserved_data[0].reserved_qty else 0.0
    
    def update_reserved_qty_for_production(self, update_qty=True):
        """
        Override to match parent signature.
        Use parent's method for production reservation.
        """
        super(CustomBin, self).update_reserved_qty_for_production(update_qty=update_qty)
    
    def update_reserved_qty_for_sub_contracting(self, update_qty=True):
        """
        Override to match parent signature with update_qty parameter.
        Use parent's method for subcontracting reservation.
        """
        super(CustomBin, self).update_reserved_qty_for_sub_contracting(update_qty=update_qty)
