import frappe
from frappe import _
from frappe.utils import flt

def execute(filters=None):
    if not filters:
        return [], []

    columns = [
        {"label": _("Project"), "fieldname": "project", "fieldtype": "Link", "options": "Project", "width": 160},
        {"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 150},
        {"label": _("Total Budget"), "fieldname": "budget", "fieldtype": "Currency", "width": 120},
        {"label": _("Total Sales"), "fieldname": "sales", "fieldtype": "Currency", "width": 120},
        {"label": _("Total Costs"), "fieldname": "costs", "fieldtype": "Currency", "width": 120},
        {"label": _("Real Profit"), "fieldname": "real_profit", "fieldtype": "Currency", "width": 120},
        {"label": _("Projected Profit"), "fieldname": "projected_profit", "fieldtype": "Currency", "width": 120},
        {"label": _("Utilization"), "fieldname": "utilization", "fieldtype": "Percent", "width": 100}
    ]

    data = get_data(filters)
    report_summary = get_summary(filters, data)
    
    return columns, data, None, None, report_summary

def get_data(filters):
    from_date = filters.get("from_date")
    to_date = filters.get("to_date")
    customer = filters.get("customer")
    project = filters.get("project")

    # Get Sales
    sql_sales = """
        SELECT 
            project, 
            customer,
            SUM(grand_total) as sales
        FROM `tabSales Invoice`
        WHERE posting_date BETWEEN %(from_date)s AND %(to_date)s
        AND docstatus = 1
    """
    params = {"from_date": from_date, "to_date": to_date}
    if customer:
        sql_sales += " AND customer = %(customer)s"
        params["customer"] = customer
    if project:
        sql_sales += " AND project = %(project)s"
        params["project"] = project
    sql_sales += " GROUP BY project, customer"
    
    sales_data = frappe.db.sql(sql_sales, params, as_dict=True)

    # Get Costs
    sql_costs = """
        SELECT 
            project,
            SUM(grand_total) as costs
        FROM `tabPurchase Invoice`
        WHERE posting_date BETWEEN %(from_date)s AND %(to_date)s
        AND docstatus = 1
    """
    if project:
        sql_costs += " AND project = %(project)s"
    elif customer:
        sql_costs += " AND project IN (SELECT name FROM tabProject WHERE customer = %(customer)s)"
    
    sql_costs += " GROUP BY project"
    costs_data = frappe.db.sql(sql_costs, params, as_dict=True)
    costs_map = {d.project: d.costs for d in costs_data}

    # Get Budgets (Estimated Cost)
    projects = list(set([d.project for d in sales_data] + [d.project for d in costs_data if d.project]))
    budget_map = {}
    if projects:
        placeholders = ', '.join(['%s'] * len(projects))
        budget_data = frappe.db.sql(f"""
            SELECT name, estimated_costing 
            FROM tabProject 
            WHERE name IN ({placeholders})
        """, tuple(projects), as_dict=True)
        budget_map = {d.name: d.estimated_costing for d in budget_data}

    data = []
    
    unique_keys = {}
    for s in sales_data:
        unique_keys[(s.project, s.customer)] = {"sales": s.sales, "costs": 0}
    
    for c in costs_data:
        if not c.project: continue
        cust = frappe.db.get_value("Project", c.project, "customer")
        key = (c.project, cust)
        if key in unique_keys:
            unique_keys[key]["costs"] = c.costs
        else:
            unique_keys[key] = {"sales": 0, "costs": c.costs}

    for (p, c), vals in unique_keys.items():
        budget = flt(budget_map.get(p, 0))
        costs = flt(vals["costs"])
        sales = flt(vals["sales"])
        util = (costs / budget * 100) if budget > 0 else 0.0
        
        real_profit = sales - costs
        projected_profit = sales - budget

        data.append({
            "project": p,
            "customer": c,
            "budget": budget,
            "sales": sales,
            "costs": costs,
            "real_profit": real_profit,
            "projected_profit": projected_profit,
            "utilization": util
        })
    
    return data

def get_summary(filters, data):
    total_sales = sum(flt(d.get("sales")) for d in data)
    total_costs = sum(flt(d.get("costs")) for d in data)
    total_budget = sum(flt(d.get("budget")) for d in data)
    
    real_profit = total_sales - total_costs
    projected_profit = total_sales - total_budget
    
    return [
        {"value": real_profit, "indicator": "green" if real_profit >= 0 else "red", "label": _("Real Profit"), "datatype": "Currency"},
        {"value": projected_profit, "indicator": "blue" if projected_profit >= 0 else "orange", "label": _("Projected Profit"), "datatype": "Currency"},
        {"value": total_budget, "indicator": "purple", "label": _("Total Budget"), "datatype": "Currency"}
    ]
