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
        {"label": _("Against Account"), "fieldname": "credit_to", "fieldtype": "Data", "width": 160},
        {"label": _("Address"), "fieldname": "address_display", "fieldtype": "Data", "width": 180},
        {"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 130},
        {"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 160},
        {"label": _("Qty"), "fieldname": "qty", "fieldtype": "Float", "width": 80},
        {"label": _("Rate"), "fieldname": "rate", "fieldtype": "Currency", "width": 110},
        {"label": _("Amount"), "fieldname": "amount", "fieldtype": "Currency", "width": 120},
        {"label": _("Payment"), "fieldname": "paid_amount", "fieldtype": "Currency", "width": 120},
        {"label": _("Balance"), "fieldname": "outstanding_amount", "fieldtype": "Currency", "width": 120}
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
            pi.posting_date, 
            'Purchase Invoice' as voucher_type,
            pi.name, 
            pi.credit_to,
            pi.address_display,
            items.item_code, 
            items.item_name,
            items.qty, 
            items.rate, 
            items.amount,
            pi.paid_amount,
            pi.outstanding_amount
        FROM `tabPurchase Invoice` pi
        JOIN `tabPurchase Invoice Item` items ON items.parent = pi.name
        WHERE pi.posting_date BETWEEN %(from_date)s AND %(to_date)s
        AND pi.docstatus = 1
    """
    params = {"from_date": from_date, "to_date": to_date}
    if supplier:
        sql += " AND pi.supplier = %(supplier)s"
        params["supplier"] = supplier
    if project:
        sql += " AND pi.project = %(project)s"
        params["project"] = project
    
    sql += " ORDER BY pi.posting_date DESC, pi.name DESC"
    
    return frappe.db.sql(sql, params, as_dict=True)

def get_summary(filters, data):
    total_costs = sum(flt(d.get("amount")) for d in data)
    items_count = len(set(d.get("item_code") for d in data if d.get("item_code")))
    invoices_count = len(set(d.get("name") for d in data if d.get("name")))

    currency = frappe.defaults.get_global_default("currency") or "USD"
    
    return [
        {"value": total_costs, "indicator": "red", "label": _("Total Costs"), "datatype": "Currency", "currency": currency},
        {"value": items_count, "indicator": "blue", "label": _("Items"), "datatype": "Int"},
        {"value": invoices_count, "indicator": "orange", "label": _("Vouchers"), "datatype": "Int"}
    ]
