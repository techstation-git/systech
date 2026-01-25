import frappe
from frappe import _
from frappe.utils import flt

def execute(filters=None):
    if filters is None:
        filters = {}

    columns = get_columns()
    data, items_count, vouchers_count = get_data(filters)
    report_summary = get_summary(data, items_count, vouchers_count)
    
    return columns, data, None, None, report_summary

def get_columns():
    return [
        {"label": _("Project"), "fieldname": "project", "fieldtype": "Link", "options": "Project", "width": 160},
        {"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 150},
        {"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 150},
        {"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 150},
        {"label": _("Sales Qty"), "fieldname": "sales_qty", "fieldtype": "Float", "width": 100},
        {"label": _("Sales Amount"), "fieldname": "sales_amount", "fieldtype": "Currency", "width": 120},
        {"label": _("Cost Qty"), "fieldname": "cost_qty", "fieldtype": "Float", "width": 100},
        {"label": _("Cost Amount"), "fieldname": "cost_amount", "fieldtype": "Currency", "width": 120},
        {"label": _("Profit"), "fieldname": "profit", "fieldtype": "Currency", "width": 120}
    ]

def get_data(filters):
    customer = filters.get("customer")
    project = filters.get("project")
    from_date = filters.get("from_date")
    to_date = filters.get("to_date")
    
    project_filters = {}
    if customer:
        project_filters["customer"] = customer
    if project:
        project_filters["name"] = project
        
    projects = frappe.get_all("Project", filters=project_filters, fields=["name", "customer"])
    project_names = [p.name for p in projects]
    
    if not project_names:
        return [], 0, 0

    # Date condition for SQL
    date_condition = ""
    if from_date and to_date:
        date_condition = "AND parent_si.posting_date BETWEEN %(from_date)s AND %(to_date)s"
    
    # Get Sales Invoices Items
    sales_items = frappe.db.sql(f"""
        SELECT 
            parent_si.project,
            parent_si.customer,
            parent_si.name as si_name,
            si_item.item_code,
            si_item.item_name,
            SUM(si_item.qty) as sales_qty,
            SUM(si_item.base_amount) as sales_amount
        FROM `tabSales Invoice Item` si_item
        JOIN `tabSales Invoice` parent_si ON si_item.parent = parent_si.name
        WHERE parent_si.project IN %(projects)s
        AND parent_si.docstatus = 1
        {date_condition}
        GROUP BY parent_si.project, si_item.item_code
    """, {"projects": project_names, "from_date": from_date, "to_date": to_date}, as_dict=True)

    # Date condition for costs
    cost_date_condition = ""
    if from_date and to_date:
        cost_date_condition = "AND parent_pi.posting_date BETWEEN %(from_date)s AND %(to_date)s"

    # Get Purchase Invoice Items (Costs)
    cost_items = frappe.db.sql(f"""
        SELECT 
            parent_pi.project,
            parent_pi.name as pi_name,
            pi_item.item_code,
            pi_item.item_name,
            SUM(pi_item.qty) as cost_qty,
            SUM(pi_item.base_amount) as cost_amount
        FROM `tabPurchase Invoice Item` pi_item
        JOIN `tabPurchase Invoice` parent_pi ON pi_item.parent = parent_pi.name
        WHERE parent_pi.project IN %(projects)s
        AND parent_pi.docstatus = 1
        {cost_date_condition}
        GROUP BY parent_pi.project, pi_item.item_code
    """, {"projects": project_names, "from_date": from_date, "to_date": to_date}, as_dict=True)

    # Track distinct items and vouchers
    total_items_set = set()
    total_vouchers_set = set()

    # Merge Data
    merged_data = {}
    
    # Merge Data
    merged_data = {}
    
    for s in sales_items:
        key = (s.project, s.item_code)
        merged_data[key] = {
            "project": s.project,
            "customer": s.customer,
            "item_code": s.item_code,
            "item_name": s.item_name,
            "sales_qty": s.sales_qty,
            "sales_amount": s.sales_amount,
            "cost_qty": 0.0,
            "cost_amount": 0.0
        }
        total_items_set.add(s.item_code)
        
    for c in cost_items:
        key = (c.project, c.item_code)
        total_items_set.add(c.item_code)
        if key in merged_data:
            merged_data[key]["cost_qty"] = c.cost_qty
            merged_data[key]["cost_amount"] = c.cost_amount
        else:
            cust = frappe.db.get_value("Project", c.project, "customer")
            merged_data[key] = {
                "project": c.project,
                "customer": cust,
                "item_code": c.item_code,
                "item_name": c.item_name,
                "sales_qty": 0.0,
                "sales_amount": 0.0,
                "cost_qty": c.cost_qty,
                "cost_amount": c.cost_amount
            }

    # Re-querying vouchers for accurate count
    vouchers = frappe.get_all("Sales Invoice", filters={"project": ["in", project_names], "docstatus": 1, "posting_date": ["between", [from_date, to_date]] if from_date else ["!=", ""]})
    vouchers += frappe.get_all("Purchase Invoice", filters={"project": ["in", project_names], "docstatus": 1, "posting_date": ["between", [from_date, to_date]] if from_date else ["!=", ""]})
    for v in vouchers: total_vouchers_set.add(v.name)

    data = []
    for val in merged_data.values():
        val["profit"] = flt(val["sales_amount"]) - flt(val["cost_amount"])
        data.append(val)
        
    return data, len(total_items_set), len(total_vouchers_set)

def get_summary(data, items_count, vouchers_count):
    total_costs = sum(flt(d.get("cost_amount")) for d in data)
    total_sales = sum(flt(d.get("sales_amount")) for d in data)
    real_profit = total_sales - total_costs
    
    return [
        {"value": total_costs, "indicator": "red", "label": _("Total Costs"), "datatype": "Currency"},
        {"value": items_count, "indicator": "blue", "label": _("Items"), "datatype": "Int"},
        {"value": vouchers_count, "indicator": "orange", "label": _("Vouchers"), "datatype": "Int"},
        {"value": real_profit, "indicator": "green" if real_profit >= 0 else "red", "label": _("Total Real Profit"), "datatype": "Currency"}
    ]
