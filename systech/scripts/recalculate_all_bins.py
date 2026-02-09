"""
One-time script to recalculate all bins and release stuck inventory.

Run this script after deploying the new stock reservation logic:
    bench --site YOUR_SITE execute systech.scripts.recalculate_all_bins.recalculate_all_bins

This will apply the smart reservation logic to all existing bins,
releasing stock held by old sales orders (>3 months) without delivery notes.
"""

import frappe

def recalculate_all_bins():
    """Recalculate reserved quantities for all bins using the new smart logic."""
    
    print("\n" + "="*60)
    print("Starting Bin Recalculation Process")
    print("="*60 + "\n")
    
    # Get all bins
    bins = frappe.get_all("Bin", fields=["name", "item_code", "warehouse", "reserved_qty"])
    
    total_bins = len(bins)
    processed = 0
    released_stock = 0
    
    print(f"Found {total_bins} bins to process.\n")
    
    for bin_data in bins:
        try:
            # Get the bin document
            bin_doc = frappe.get_doc("Bin", bin_data.name)
            
            # Store old reserved qty
            old_reserved = bin_data.reserved_qty or 0
            
            # Trigger recalculation (uses our CustomBin.recalculate_qty)
            bin_doc.recalculate_qty()
            
            # Get new reserved qty
            new_reserved = frappe.db.get_value("Bin", bin_data.name, "reserved_qty") or 0
            
            # Report if stock was released
            if old_reserved > new_reserved:
                released = old_reserved - new_reserved
                released_stock += released
                print(f"✓ {bin_data.item_code} ({bin_data.warehouse}): Released {released} units")
            
            processed += 1
            
            # Progress indicator every 50 bins
            if processed % 50 == 0:
                print(f"\n--- Progress: {processed}/{total_bins} bins processed ---\n")
                
        except Exception as e:
            print(f"✗ Error processing {bin_data.item_code} ({bin_data.warehouse}): {str(e)}")
            continue
    
    # Commit all changes
    frappe.db.commit()
    
    print("\n" + "="*60)
    print("Recalculation Complete!")
    print("="*60)
    print(f"\nTotal Bins Processed: {processed}/{total_bins}")
    print(f"Total Stock Released: {released_stock} units")
    print("\nAll old stuck reservations have been cleared!\n")
