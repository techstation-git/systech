import frappe
from frappe import _
from frappe.utils import flt

def execute(filters=None):
    if not filters:
        return [], []

    columns = [
        {"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
        {"label": _("Voucher Type"), "fieldname": "voucher_type", "fieldtype": "Data", "width": 120},
        {"label": _("Voucher Number"), "fieldname": "name", "fieldtype": "Dynamic Link", "options": "voucher_type", "width": 140},
        {"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 140},
        {"label": _("Project"), "fieldname": "project", "fieldtype": "Link", "options": "Project", "width": 140},
        {"label": _("Warehouse"), "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 120},
        {"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 130},
        {"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 160},
        {"label": _("Qty"), "fieldname": "qty", "fieldtype": "Float", "width": 80},
        {"label": _("Rate"), "fieldname": "rate", "fieldtype": "Currency", "width": 110},
        {"label": _("Amount"), "fieldname": "amount", "fieldtype": "Currency", "width": 120},
        {"label": _("Paid"), "fieldname": "paid_amount", "fieldtype": "Currency", "width": 120},
        {"label": _("Outstanding"), "fieldname": "outstanding_amount", "fieldtype": "Currency", "width": 120}
    ]

    data = get_data(filters)
    report_summary = get_summary(filters, data)
    
    return columns, data, None, None, report_summary

def get_data(filters):
    from_date = filters.get("from_date")
    to_date = filters.get("to_date")
    customer = filters.get("customer")
    project = filters.get("project")
    item_brand = filters.get("item_brand")

    sql = """
        SELECT 
            si.posting_date, 
            'Sales Invoice' as voucher_type,
            si.name, 
            si.customer,
            si.project,
            items.warehouse,
            items.item_code, 
            items.item_name,
            items.qty, 
            items.rate, 
            items.amount,
            si.paid_amount,
            si.outstanding_amount,
            i.item_group
        FROM `tabSales Invoice` si
        JOIN `tabSales Invoice Item` items ON items.parent = si.name
        JOIN `tabItem` i ON i.name = items.item_code
        WHERE si.posting_date BETWEEN %(from_date)s AND %(to_date)s
        AND si.docstatus = 1
    """
    params = {"from_date": from_date, "to_date": to_date}
    if customer:
        sql += " AND si.customer = %(customer)s"
        params["customer"] = customer
    if project:
        sql += " AND si.project = %(project)s"
        params["project"] = project
    if item_brand:
        sql += " AND i.item_group = %(item_brand)s"
        params["item_brand"] = item_brand
    
    sql += " ORDER BY si.posting_date DESC, si.name DESC"
    
    return frappe.db.sql(sql, params, as_dict=True)

def get_summary(filters, data):
    total_sales = sum(flt(d.get("amount")) for d in data)
    items_count = len(set(d.get("item_code") for d in data if d.get("item_code")))
    invoices_count = len(set(d.get("name") for d in data if d.get("name")))

    currency = frappe.defaults.get_global_default("currency") or "USD"
    
    return [
        {"value": total_sales, "indicator": "green", "label": _("Total Sales"), "datatype": "Currency", "currency": currency},
        {"value": items_count, "indicator": "blue", "label": _("Items"), "datatype": "Int"},
        {"value": invoices_count, "indicator": "orange", "label": _("Vouchers"), "datatype": "Int"}
    ]
