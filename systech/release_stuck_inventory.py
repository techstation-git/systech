#!/usr/bin/env python3
"""
Script to Release Inventory from Stuck Sales Orders

This script identifies submitted sales orders that do not have any associated
delivery notes and releases their reserved stock by closing/cancelling them.

Usage:
    # Dry run (preview only)
    bench --site <site-name> execute systech.release_stuck_inventory.release_stuck_inventory --kwargs "{'dry_run': True}"
    
    # Execute with default date filter (before 2026-01-01)
    bench --site <site-name> execute systech.release_stuck_inventory.release_stuck_inventory --kwargs "{'dry_run': False}"
    
    # Execute with custom date filter
    bench --site <site-name> execute systech.release_stuck_inventory.release_stuck_inventory --kwargs "{'dry_run': False, 'before_date': '2025-12-31'}"
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate
import json


def release_stuck_inventory(dry_run=True, before_date="2026-01-01"):
    """
    Identify and release inventory from stuck sales orders.
    
    Args:
        dry_run (bool): If True, only preview affected orders without making changes
        before_date (str): Only process sales orders created before this date (YYYY-MM-DD)
    
    Returns:
        dict: Summary of the operation
    """
    frappe.init(site=frappe.local.site)
    frappe.connect()
    
    print("\n" + "="*70)
    print("RELEASE STUCK INVENTORY FROM SALES ORDERS")
    print("="*70)
    print(f"Mode: {'DRY RUN (Preview Only)' if dry_run else 'EXECUTE'}")
    print(f"Date Filter: Processing orders before {before_date}")
    print("="*70 + "\n")
    
    # Step 1: Find stuck sales orders
    stuck_orders = find_stuck_sales_orders(before_date)
    
    if not stuck_orders:
        print("✓ No stuck sales orders found. All inventory is clean!")
        return {
            "status": "success",
            "message": "No stuck orders found",
            "orders_processed": 0
        }
    
    print(f"Found {len(stuck_orders)} stuck sales order(s):\n")
    
    # Display details
    total_reserved_qty = 0
    for order in stuck_orders:
        print(f"  • {order['name']}")
        print(f"    Customer: {order['customer']}")
        print(f"    Date: {order['transaction_date']}")
        print(f"    Status: {order['status']} | Workflow: {order['workflow_state']}")
        print(f"    Total Qty: {order['total_qty']} | Amount: {order['currency']} {order['grand_total']:,.2f}")
        
        # Get items for this order
        items = get_order_items(order['name'])
        print(f"    Items:")
        for item in items:
            print(f"      - {item['item_code']}: {item['qty']} units in {item['warehouse']}")
            total_reserved_qty += flt(item['qty'])
        print()
    
    print(f"Total Reserved Quantity to be Released: {total_reserved_qty}\n")
    print("-"*70 + "\n")
    
    if dry_run:
        print("⚠ DRY RUN MODE - No changes made")
        print("\nTo execute the release, run with dry_run=False:")
        print('bench --site <site-name> execute systech.release_stuck_inventory.release_stuck_inventory --kwargs "{\'dry_run\': False}"')
        return {
            "status": "preview",
            "message": "Dry run completed",
            "orders_found": len(stuck_orders),
            "total_qty_reserved": total_reserved_qty,
            "orders": stuck_orders
        }
    
    # Step 2: Execute release
    print("Proceeding with inventory release...\n")
    
    released_orders = []
    failed_orders = []
    
    for order in stuck_orders:
        try:
            result = release_order_stock(order['name'])
            released_orders.append(order['name'])
            print(f"✓ Released: {order['name']}")
        except Exception as e:
            failed_orders.append({"name": order['name'], "error": str(e)})
            print(f"✗ Failed: {order['name']} - {str(e)}")
            frappe.log_error(
                title=f"Failed to release stock for {order['name']}",
                message=str(e)
            )
    
    frappe.db.commit()
    
    print("\n" + "="*70)
    print("OPERATION COMPLETE")
    print("="*70)
    print(f"Total Orders Processed: {len(stuck_orders)}")
    print(f"Successfully Released: {len(released_orders)}")
    print(f"Failed: {len(failed_orders)}")
    print("="*70 + "\n")
    
    if failed_orders:
        print("Failed Orders:")
        for failure in failed_orders:
            print(f"  • {failure['name']}: {failure['error']}")
    
    return {
        "status": "completed",
        "message": "Inventory release completed",
        "orders_processed": len(stuck_orders),
        "successfully_released": len(released_orders),
        "failed": len(failed_orders),
        "released_orders": released_orders,
        "failed_orders": failed_orders
    }


def find_stuck_sales_orders(before_date):
    """
    Find submitted sales orders without any delivery notes.
    
    Args:
        before_date (str): Only return orders created before this date
    
    Returns:
        list: List of stuck sales orders
    """
    query = """
        SELECT 
            so.name,
            so.customer,
            so.transaction_date,
            so.workflow_state,
            so.status,
            so.total_qty,
            so.grand_total,
            so.currency
        FROM `tabSales Order` so
        WHERE so.docstatus = 1
        AND so.status NOT IN ('Cancelled', 'Closed')
        AND so.transaction_date < %(before_date)s
        AND so.name NOT IN (
            SELECT DISTINCT IFNULL(against_sales_order, '')
            FROM `tabDelivery Note Item`
            WHERE against_sales_order IS NOT NULL
            AND against_sales_order != ''
        )
        ORDER BY so.transaction_date ASC
    """
    
    return frappe.db.sql(query, {"before_date": before_date}, as_dict=True)


def get_order_items(sales_order_name):
    """
    Get all items from a sales order.
    
    Args:
        sales_order_name (str): Name of the sales order
    
    Returns:
        list: List of items with details
    """
    return frappe.db.sql("""
        SELECT 
            item_code,
            item_name,
            qty,
            warehouse,
            delivered_qty
        FROM `tabSales Order Item`
        WHERE parent = %(parent)s
        ORDER BY idx
    """, {"parent": sales_order_name}, as_dict=True)


def release_order_stock(sales_order_name):
    """
    Release stock by closing/cancelling a sales order.
    
    Args:
        sales_order_name (str): Name of the sales order
    
    Returns:
        dict: Result of the operation
    """
    # Get the sales order document
    doc = frappe.get_doc("Sales Order", sales_order_name)
    
    # Check current status
    if doc.status in ("Cancelled", "Closed"):
        return {
            "status": "skipped",
            "message": f"Order already {doc.status.lower()}"
        }
    
    # Store items for bin update
    items_to_update = []
    for item in doc.items:
        if item.item_code and item.warehouse:
            items_to_update.append({
                "item_code": item.item_code,
                "warehouse": item.warehouse,
                "qty": flt(item.qty) - flt(item.delivered_qty)
            })
    
    # Close the sales order to release stock
    # We use db_set to update without triggering full save
    doc.db_set("status", "Closed", update_modified=True)
    doc.db_set("workflow_state", "Cancelled", update_modified=False)
    
    # Force update reserved quantities
    try:
        doc.update_reserved_qty()
    except Exception as e:
        frappe.log_error(
            title=f"Reserved Qty Update Failed for {sales_order_name}",
            message=str(e)
        )
    
    # Update Bin for each item to ensure reserved stock is released
    from erpnext.stock.utils import get_bin
    
    for item in items_to_update:
        try:
            bin_obj = get_bin(item['item_code'], item['warehouse'])
            bin_obj.update_reserved_stock()
        except Exception as e:
            frappe.log_error(
                title=f"Bin Update Failed for {item['item_code']} in {item['warehouse']}",
                message=str(e)
            )
    
    return {
        "status": "success",
        "message": f"Successfully released stock from {sales_order_name}",
        "items_updated": len(items_to_update)
    }


# Convenience function for bench console
def run_dry_run():
    """Quick dry run from bench console"""
    return release_stuck_inventory(dry_run=True)


def run_execute(before_date="2026-01-01"):
    """Execute release from bench console"""
    return release_stuck_inventory(dry_run=False, before_date=before_date)
