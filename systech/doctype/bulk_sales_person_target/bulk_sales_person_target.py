# -*- coding: utf-8 -*-
# Copyright (c) 2026, TechStation and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.utils import flt

class BulkSalesPersonTarget(Document):
    pass

@frappe.whitelist()
def preview_changes(fiscal_year, item_group, target_type, amount):
    """
    Preview which Sales People will be affected by the bulk target update.
    Returns a list of Sales People with current vs new targets.
    """
    # Get all enabled Sales People (excluding groups)
    sales_people = frappe.get_all("Sales Person",
        filters={"enabled": 1, "is_group": 0},
        fields=["name", "sales_person_name"]
    )
    
    # Calculate yearly target
    yearly_target = flt(amount) * 12 if target_type == "Monthly" else flt(amount)
    
    preview_data = []
    for sp in sales_people:
        # Check if this person already has a target for this year/item group
        current_target = frappe.db.get_value("Target Detail",
            {"parent": sp.name, "fiscal_year": fiscal_year, "item_group": item_group},
            "target_amount"
        )
        
        preview_data.append({
            "sales_person": sp.name,
            "sales_person_name": sp.sales_person_name,
            "current_target": flt(current_target) if current_target else 0,
            "new_target": yearly_target,
            "status": "Override" if current_target else "New"
        })
    
    return preview_data

@frappe.whitelist()
def apply_targets(fiscal_year, item_group, target_type, amount, selected_people):
    """
    Apply targets to the selected Sales People.
    selected_people should be a JSON array of sales person names.
    """
    import json
    selected = json.loads(selected_people) if isinstance(selected_people, str) else selected_people
    
    # Calculate yearly target
    yearly_target = flt(amount) * 12 if target_type == "Monthly" else flt(amount)
    
    # Ensure Monthly Equal distribution exists
    distribution_id = ensure_monthly_equal_distribution(fiscal_year)
    
    updated_count = 0
    for sp_name in selected:
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
        
        # Add 12 equal percentages (8.33% each, totaling ~100%)
        for month in range(1, 13):
            dist.append("percentages", {
                "month": frappe.utils.get_month_name(month),
                "percentage_allocation": 8.33
            })
        
        dist.insert(ignore_permissions=True)
        frappe.db.commit()
    
    return dist_name
