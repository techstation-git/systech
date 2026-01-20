# -*- coding: utf-8 -*-
# Copyright (c) 2026, TechStation and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import flt
import calendar

@frappe.whitelist()
def apply_bulk_target(fiscal_year, item_group, target_type, amount, sales_people):
    """
    Apply target to selected Sales People from list view.
    """
    import json
    if isinstance(sales_people, str):
        sales_people = json.loads(sales_people)
    
    # Calculate yearly target
    yearly_target = flt(amount) * 12 if target_type == "Monthly" else flt(amount)
    
    # Ensure Monthly Equal distribution exists
    distribution_id = ensure_monthly_equal_distribution(fiscal_year)
    
    updated_count = 0
    for sp_name in sales_people:
        sp_doc = frappe.get_doc("Sales Person", sp_name)
        
        # Check if target row exists
        existing_target = None
        for target in sp_doc.targets:
            if target.fiscal_year == fiscal_year and target.item_group == item_group:
                existing_target = target
                break
        
        if existing_target:
            # Update existing
            existing_target.target_amount = yearly_target
            existing_target.distribution_id = distribution_id
        else:
            # Add new row
            sp_doc.append("targets", {
                "fiscal_year": fiscal_year,
                "item_group": item_group,
                "target_amount": yearly_target,
                "distribution_id": distribution_id
            })
        
        sp_doc.save(ignore_permissions=True)
        updated_count += 1
    
    frappe.db.commit()
    return {"status": "success", "updated_count": updated_count}

def ensure_monthly_equal_distribution(fiscal_year):
    """
    Ensure a 'Monthly Equal' distribution exists for the given fiscal year.
    Returns the distribution ID.
    """
    dist_name = f"Monthly Equal - {fiscal_year}"
    
    if not frappe.db.exists("Monthly Distribution", dist_name):
        dist = frappe.new_doc("Monthly Distribution")
        dist.distribution_id = dist_name
        dist.fiscal_year = fiscal_year
        
        # Add 12 equal percentages totaling exactly 100%
        # 11 months at 8.33%, last month at 8.37% = 100.00%
        for month_num in range(1, 13):
            percentage = 8.37 if month_num == 12 else 8.33
            dist.append("percentages", {
                "month": calendar.month_name[month_num],
                "percentage_allocation": percentage
            })
        
        dist.insert(ignore_permissions=True)
        frappe.db.commit()
    
    return dist_name
