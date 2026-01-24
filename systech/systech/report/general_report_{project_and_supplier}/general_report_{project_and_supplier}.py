import frappe
from frappe import _
from frappe.utils import flt

def execute(filters=None):
    if not filters:
        return [], []

    columns = [
        {"label": _("Supplier"), "fieldname": "supplier", "fieldtype": "Link", "options": "Supplier", "width": 160},
        {"label": _("Project"), "fieldname": "project", "fieldtype": "Link", "options": "Project", "width": 160},
        {"label": _("Total Costs"), "fieldname": "costs", "fieldtype": "Currency", "width": 130},
        {"label": _("Total Paid"), "fieldname": "paid_amount", "fieldtype": "Currency", "width": 130},
        {"label": _("Total Outstanding"), "fieldname": "outstanding_amount", "fieldtype": "Currency", "width": 130}
    ]

    data = get_data(filters)
    report_summary = get_summary(filters, data)
    
    return columns, data, None, None, report_summary

def get_data(filters):
    from_date = filters.get("from_date")
    to_date = filters.get("to_date")
    supplier = filters.get("supplier")
    project = filters.get("project")

    sql = """
        SELECT 
            supplier, 
            project,
            SUM(grand_total) as costs,
            SUM(paid_amount) as paid_amount,
            SUM(outstanding_amount) as outstanding_amount
        FROM `tabPurchase Invoice`
        WHERE posting_date BETWEEN %(from_date)s AND %(to_date)s
        AND docstatus = 1
    """
    params = {"from_date": from_date, "to_date": to_date}
    if supplier:
        sql += " AND supplier = %(supplier)s"
        params["supplier"] = supplier
    if project:
        sql += " AND project = %(project)s"
        params["project"] = project
    
    sql += " GROUP BY supplier, project ORDER BY supplier, project"
    
    return frappe.db.sql(sql, params, as_dict=True)

def get_summary(filters, data):
    total_costs = sum(flt(d.get("costs")) for d in data)
    total_paid = sum(flt(d.get("paid_amount")) for d in data)
    total_outstanding = sum(flt(d.get("outstanding_amount")) for d in data)

    currency = frappe.defaults.get_global_default("currency") or "USD"
    
    return [
        {"value": total_costs, "indicator": "red", "label": _("Total Costs"), "datatype": "Currency", "currency": currency},
        {"value": total_paid, "indicator": "green", "label": _("Total Paid"), "datatype": "Currency", "currency": currency},
        {"value": total_outstanding, "indicator": "orange", "label": _("Total Outstanding"), "datatype": "Currency", "currency": currency}
    ]
