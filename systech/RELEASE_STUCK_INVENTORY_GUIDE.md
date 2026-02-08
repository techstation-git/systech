# Release Stuck Inventory - Usage Guide

## Overview

The `release_stuck_inventory.py` script identifies and releases inventory from sales orders that don't have associated delivery notes. This resolves the issue where old sales orders keep stock reserved, blocking new orders from being fulfilled.

## How It Works

The script:
1. **Identifies** submitted sales orders without delivery notes
2. **Displays** a detailed list of affected orders for review
3. **Releases** stock by closing/cancelling the identified orders
4. **Updates** the Bin table to reflect released inventory

## Usage

### Step 1: Dry Run (Preview Only)

First, run in dry-run mode to see which orders will be affected:

```bash
cd /home/abeddy/techstation/apps/systech
bench --site techstation.com execute systech.release_stuck_inventory.release_stuck_inventory --kwargs "{'dry_run': True}"
```

This will show you:
- List of stuck sales orders
- Customer names and order dates
- Items and quantities reserved
- Total reserved quantity

**No changes are made in dry-run mode.**

### Step 2: Review the List

Carefully review the output to ensure:
- These are indeed legacy/stuck orders
- The orders should be cancelled
- The inventory should be released

### Step 3: Execute the Release

Once confirmed, run without dry_run to execute:

```bash
bench --site techstation.com execute systech.release_stuck_inventory.release_stuck_inventory --kwargs "{'dry_run': False}"
```

This will:
- Close/cancel the identified orders
- Release the reserved stock
- Update bin quantities
- Show a summary of results

### Custom Date Filter

By default, the script processes orders before `2026-01-01`. To use a custom date:

```bash
# Process orders before a specific date
bench --site techstation.com execute systech.release_stuck_inventory.release_stuck_inventory --kwargs "{'dry_run': True, 'before_date': '2025-12-31'}"
```

## Alternative: Using Bench Console

You can also run from the bench console:

```bash
bench --site techstation.com console
```

Then in the console:

```python
# Dry run
from systech.release_stuck_inventory import run_dry_run
result = run_dry_run()

# Execute
from systech.release_stuck_inventory import run_execute
result = run_execute(before_date="2026-01-01")
```

## What Happens to the Orders

When the script releases inventory:
1. Sales Order `status` is set to `"Closed"`
2. Sales Order `workflow_state` is set to `"Cancelled"`
3. The `update_reserved_qty()` method is called on the order
4. Each item's Bin record is updated to release reserved stock
5. New orders can now access this inventory

## Verification

After running the script, verify:

1. **Check released orders**: They should show Status = "Closed"
2. **Try submitting blocked orders**: New sales orders should now submit successfully
3. **Check stock levels**: Available stock should increase

## Example Output

```
======================================================================
RELEASE STUCK INVENTORY FROM SALES ORDERS
======================================================================
Mode: DRY RUN (Preview Only)
Date Filter: Processing orders before 2026-01-01
======================================================================

Found 3 stuck sales order(s):

  • SAL-ORD-2025-00123
    Customer: ABC Company
    Date: 2025-11-15
    Status: On Hold | Workflow: Approved
    Total Qty: 50.0 | Amount: USD 5,000.00
    Items:
      - ITEM-001: 30.0 units in Main Warehouse
      - ITEM-002: 20.0 units in Main Warehouse

Total Reserved Quantity to be Released: 50.0

⚠ DRY RUN MODE - No changes made
```

## Troubleshooting

### No stuck orders found
- Check the date filter - orders might be after the cutoff date
- Verify sales orders exist without delivery notes
- Ensure orders are in submitted status (docstatus = 1)

### Script fails to execute
- Check that you have Sales Manager permissions
- Ensure the site name is correct
- Check error logs: `bench --site techstation.com show-log`

## Safety Features

✓ **Dry-run mode**: Preview before making changes  
✓ **Date filtering**: Only process old orders  
✓ **Detailed logging**: All failures are logged  
✓ **Transaction safety**: Changes are committed together  
✓ **Error handling**: Failed orders don't stop the entire process
