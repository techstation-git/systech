# -*- coding: utf-8 -*-
# Copyright (c) 2026, TechStation and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe

def auto_assign_sales_team(doc, method=None):
    """Auto-assign creator to customer's sales team"""
    # Only auto-assign if sales_team is empty
    if not doc.sales_team and frappe.session.user != "Administrator":
        # Get employee linked to current user
        employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user})
        
        if employee:
            # Get Sales Person linked to this employee
            sales_person = frappe.db.get_value("Sales Person", {"employee": employee})
            
            if sales_person:
                doc.append("sales_team", {
                    "sales_person": sales_person,
                    "allocated_percentage": 100,
                    "allocated_amount": 0
                })
