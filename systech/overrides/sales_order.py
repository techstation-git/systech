import frappe
from erpnext.selling.doctype.sales_order.sales_order import SalesOrder

class CustomSalesOrder(SalesOrder):
    """
    Custom Sales Order to disable automatic stock reservation.
    Stock reservation now happens only at Delivery Note level.
    """
    
    def update_reserved_qty(self, so_item_rows=None):
        """
        Override ERPNext's update_reserved_qty to prevent stock reservation at SO level.
        
        Stock reservation is disabled for Sales Orders. It will only happen when
        Delivery Notes are created. This prevents old SOs from blocking inventory.
        
        Per client requirement (Hazem): Stock reservation should happen at DN level only.
        """
        # Completely disable reserved quantity updates for Sales Orders
        # Do nothing - no reservation should happen
        pass
    
    def update_reserved_qty_for_subcontract(self):
        """
        Override to prevent subcontract reservation as well.
        """
        pass
    
    def on_submit(self):
        """
        Override on_submit to skip stock reservation completely.
        """
        # Store the original method reference
        original_update_bin = None
        
        try:
            # Temporarily disable update_bin if it exists
            if hasattr(self, 'update_bin'):
                original_update_bin = self.update_bin
                self.update_bin = lambda: None
            
            # Call parent's on_submit
            # We use super() to call the grandparent if needed to skip reservation logic
            super(CustomSalesOrder, self).on_submit()
            
        finally:
            # Restore original method if we changed it
            if original_update_bin:
                self.update_bin = original_update_bin
        
        # After submit, ensure no reserved qty was set
        # Force clear any reserved_qty that might have been set
        self._clear_reserved_qty_in_bin()
    
    def on_update_after_submit(self):
        """
        Override to prevent reservation updates after submission.
        """
        # Call parent but skip reservation
        # First backup and disable update methods
        original_update_reserved = self.update_reserved_qty
        self.update_reserved_qty = lambda so_item_rows=None: None
        
        try:
            super(CustomSalesOrder, self).on_update_after_submit()
        finally:
            self.update_reserved_qty = original_update_reserved
        
        # Clear any reserved qty that might have been set
        self._clear_reserved_qty_in_bin()
    
    def on_cancel(self):
        """
        Override on_cancel to handle cancellation without reservation issues.
        """
        # Since we never reserved stock, just call parent
        super(CustomSalesOrder, self).on_cancel()
    
    def _clear_reserved_qty_in_bin(self):
        """
        Helper method to forcefully clear any reserved_qty from Bin
        that might have been set by ERPNext's internal logic.
        """
        if not self.items:
            return
        
        from erpnext.stock.utils import get_bin
        
        for item in self.items:
            if not item.item_code or not item.warehouse:
                continue
            
            try:
                # Get the bin and force update reserved stock to exclude this SO
                bin_obj = get_bin(item.item_code, item.warehouse)
                # Update reserved stock - this will recalculate from all other SOs
                # but our SO won't contribute because update_reserved_qty does nothing
                bin_obj.update_reserved_stock()
            except Exception as e:
                # Log but don't fail
                frappe.log_error(
                    title=f"Failed to clear reserved qty for {item.item_code}",
                    message=str(e)
                )
