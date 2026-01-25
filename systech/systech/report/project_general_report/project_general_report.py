import frappe
from frappe import _
from frappe.utils import flt

def execute(filters=None):
    if filters is None:
        filters = {}

    columns = get_columns()
    data, items_count, vouchers_count = get_data(filters)
    
    # Calculate Profit and totals for summary
    report_summary = get_summary(data, items_count, vouchers_count)
    
    return columns, data, None, None, report_summary

def get_columns():
    return [
        {"label": _("Project"), "fieldname": "project", "fieldtype": "Link", "options": "Project", "width": 160},
        {"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 150},
        {"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 100},
        {"label": _("Total Budget"), "fieldname": "budget", "fieldtype": "Currency", "width": 120},
        {"label": _("Total Sales"), "fieldname": "sales", "fieldtype": "Currency", "width": 120},
        {"label": _("Total Costs"), "fieldname": "costs", "fieldtype": "Currency", "width": 120},
        {"label": _("Real Profit"), "fieldname": "real_profit", "fieldtype": "Currency", "width": 120},
        {"label": _("Utilization %"), "fieldname": "utilization", "fieldtype": "Percent", "width": 100}
    ]

def get_data(filters):
    customer = filters.get("customer")
    project = filters.get("project")
    from_date = filters.get("from_date")
    to_date = filters.get("to_date")
    
    # Base Projects query
    project_filters = {}
    if customer:
        project_filters["customer"] = customer
    if project:
        project_filters["name"] = project
        
    projects = frappe.get_all("Project", filters=project_filters, fields=["name", "customer", "status", "estimated_costing"])
    
    data = []
    total_items_set = set()
    total_vouchers_set = set()
    
    for p in projects:
        # Get Sales
        sales_query_filters = {"project": p.name, "docstatus": 1}
        if from_date and to_date:
            sales_query_filters["posting_date"] = ["between", [from_date, to_date]]
            
        sales_invoices = frappe.get_all("Sales Invoice", filters=sales_query_filters, fields=["name", "grand_total"])
        sales = sum(flt(si.grand_total) for si in sales_invoices)
        
        # Get Costs
        costs_query_filters = {"project": p.name, "docstatus": 1}
        if from_date and to_date:
            costs_query_filters["posting_date"] = ["between", [from_date, to_date]]
            
        purchase_invoices = frappe.get_all("Purchase Invoice", filters=costs_query_filters, fields=["name", "grand_total"])
        costs = sum(flt(pi.grand_total) for pi in purchase_invoices)
        
        # Track for summary
        for si in sales_invoices: total_vouchers_set.add(si.name)
        for pi in purchase_invoices: total_vouchers_set.add(pi.name)
        
        # Get unique items count for these vouchers
        if sales_invoices or purchase_invoices:
            invoice_names = [si.name for si in sales_invoices] + [pi.name for pi in purchase_invoices]
            items = frappe.get_all("Sales Invoice Item", filters={"parent": ["in", invoice_names]}, fields=["item_code"])
            items += frappe.get_all("Purchase Invoice Item", filters={"parent": ["in", invoice_names]}, fields=["item_code"])
            for itm in items: total_items_set.add(itm.item_code)

        budget = flt(p.estimated_costing)
        real_profit = flt(sales) - flt(costs)
        utilization = (flt(costs) / budget * 100) if budget > 0 else 0.0
        
        data.append({
            "project": p.name,
            "customer": p.customer,
            "status": p.status,
            "budget": budget,
            "sales": sales,
            "costs": costs,
            "real_profit": real_profit,
            "utilization": utilization
        })
        
    return data, len(total_items_set), len(total_vouchers_set)

def get_summary(data, items_count, vouchers_count):
    total_sales = sum(flt(d.get("sales")) for d in data)
    total_costs = sum(flt(d.get("costs")) for d in data)
    
    real_profit = total_sales - total_costs
    
    return [
        {"value": total_costs, "indicator": "red", "label": _("Total Costs"), "datatype": "Currency"},
        {"value": items_count, "indicator": "blue", "label": _("Items"), "datatype": "Int"},
        {"value": vouchers_count, "indicator": "orange", "label": _("Vouchers"), "datatype": "Int"},
        {"value": real_profit, "indicator": "green" if real_profit >= 0 else "red", "label": _("Total Real Profit"), "datatype": "Currency"}
    ]
