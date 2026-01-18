
import frappe


def get_permission_query_conditions(user, doctype=None):
    if not user:
        user = frappe.session.user

    # If user is System Manager, Sales Manager or Administrator, allow all
    roles = frappe.get_roles(user)
    if "System Manager" in roles or "Sales Manager" in roles or "Administrator" in roles:
        return ""

    # Check if user is linked to a Sales Person

    conditions = []
    
    # 1. By Employee (Strongest Link)
    employee = frappe.db.get_value("Employee", {"user_id": user}, "name")
    if employee:
        conditions.append(f'`tabSales Person`.employee = "{employee}"')
        
    # 2. By User matching Sales Person Name (or part of it)
    # Get User Full Name
    # Note: We use frappe.db.escape to avoid injection
    user_full_name = frappe.db.get_value("User", user, "full_name")
    if user_full_name:
         conditions.append(f'`tabSales Person`.sales_person_name = "{frappe.db.escape(user_full_name)}"')
    
    # 3. By User Email/ID directly
    conditions.append(f'`tabSales Person`.sales_person_name = "{frappe.db.escape(user)}"')
    
    # 4. By Owner
    conditions.append(f'`tabSales Person`.owner = "{frappe.db.escape(user)}"')

    return f"({' OR '.join(conditions)})"


def get_permission_query_conditions_sales_order(user):
    """Permission query for Sales Order - restrict to own sales only"""
    if not user:
        user = frappe.session.user

    # If user is System Manager, Sales Manager or Administrator, allow all
    roles = frappe.get_roles(user)
    if "System Manager" in roles or "Sales Manager" in roles or "Administrator" in roles:
        return ""

    # Find the Sales Person linked to this user
    from systech.services.api import get_current_salesperson
    salesperson = get_current_salesperson()
    
    if not salesperson:
        # No linked salesperson - show nothing
        return "1=0"
    
    # Only show Sales Orders where this salesperson is in the Sales Team
    return f"""(`tabSales Order`.name IN (
        SELECT parent 
        FROM `tabSales Team` 
        WHERE parenttype = 'Sales Order' 
        AND sales_person = {frappe.db.escape(salesperson)}
    ))"""


def get_permission_query_conditions_sales_invoice(user):
    """Permission query for Sales Invoice - restrict to own sales only"""
    if not user:
        user = frappe.session.user

    # If user is System Manager, Sales Manager or Administrator, allow all
    roles = frappe.get_roles(user)
    if "System Manager" in roles or "Sales Manager" in roles or "Administrator" in roles:
        return ""

    # Find the Sales Person linked to this user
    from systech.services.api import get_current_salesperson
    salesperson = get_current_salesperson()
    
    if not salesperson:
        return "1=0"
    
    # Only show Sales Invoices where this salesperson is in the Sales Team
    return f"""(`tabSales Invoice`.name IN (
        SELECT parent 
        FROM `tabSales Team` 
        WHERE parenttype = 'Sales Invoice' 
        AND sales_person = {frappe.db.escape(salesperson)}
    ))"""


def get_permission_query_conditions_quotation(user):
    """Permission query for Quotation - restrict to own sales only"""
    if not user:
        user = frappe.session.user

    # If user is System Manager, Sales Manager or Administrator, allow all
    roles = frappe.get_roles(user)
    if "System Manager" in roles or "Sales Manager" in roles or "Administrator" in roles:
        return ""

    # Find the Sales Person linked to this user
    from systech.services.api import get_current_salesperson
    salesperson = get_current_salesperson()
    
    if not salesperson:
        return "1=0"
    
    # Only show Quotations where this salesperson is in the Sales Team
    return f"""(`tabQuotation`.name IN (
        SELECT parent 
        FROM `tabSales Team` 
        WHERE parenttype = 'Quotation' 
        AND sales_person = {frappe.db.escape(salesperson)}
    ))"""


def get_permission_query_conditions_payment_entry(user):
    """Permission query for Payment Entry - restrict to own sales only"""
    if not user:
        user = frappe.session.user

    # If user is System Manager, Sales Manager or Administrator, allow all
    roles = frappe.get_roles(user)
    if "System Manager" in roles or "Sales Manager" in roles or "Administrator" in roles or "Accounts Manager" in roles or "Accounts User" in roles:
        return ""

    # Find the Sales Person linked to this user
    from systech.services.api import get_current_salesperson
    salesperson = get_current_salesperson()
    
    if not salesperson:
        return "1=0"
    
    # Only show Payment Entries linked to Sales Invoices where this salesperson is in the Sales Team
    return f"""(`tabPayment Entry`.name IN (
        SELECT DISTINCT pe.name
        FROM `tabPayment Entry` pe
        INNER JOIN `tabPayment Entry Reference` per ON per.parent = pe.name
        INNER JOIN `tabSales Team` st ON st.parent = per.reference_name AND st.parenttype = per.reference_doctype
        WHERE st.sales_person = {frappe.db.escape(salesperson)}
    ))"""
