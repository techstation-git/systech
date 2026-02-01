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
        {"label": _("Supplier"), "fieldname": "supplier", "fieldtype": "Link", "options": "Supplier", "width": 160},
        {"label": _("Voucher No"), "fieldname": "voucher_no", "fieldtype": "Dynamic Link", "options": "voucher_type", "width": 140},
        {"label": _("Posting Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
        {"label": _("Brand (Item Group)"), "fieldname": "item_group", "fieldtype": "Link", "options": "Item Group", "width": 150},
        {"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 150},
        {"label": _("Qty"), "fieldname": "qty", "fieldtype": "Float", "width": 80},
        {"label": _("Rate"), "fieldname": "rate", "fieldtype": "Currency", "width": 100},
        {"label": _("Amount"), "fieldname": "amount", "fieldtype": "Currency", "width": 120}
    ]

def get_data(filters):
    supplier = filters.get("supplier")
    brand = filters.get("brand")
    from_date = filters.get("from_date")
    to_date = filters.get("to_date")
    
    date_condition = ""
    params = {}
    if from_date and to_date:
        date_condition = "AND pi.posting_date BETWEEN %(from_date)s AND %(to_date)s"
        params["from_date"] = from_date
        params["to_date"] = to_date

    sql = f"""
        SELECT 
            pi.supplier,
            pi.name as voucher_no,
            'Purchase Invoice' as voucher_type,
            pi.posting_date,
            item.item_group,
            pi_item.item_code,
            pi_item.qty,
            pi_item.base_rate as rate,
            pi_item.base_amount as amount
        FROM `tabPurchase Invoice Item` pi_item
        JOIN `tabPurchase Invoice` pi ON pi_item.parent = pi.name
        JOIN `tabItem` item ON pi_item.item_code = item.name
        WHERE pi.docstatus = 1
        {date_condition}
    """
    
    if supplier:
        sql += " AND pi.supplier = %(supplier)s"
        params["supplier"] = supplier
    if brand:
        sql += " AND item.item_group = %(brand)s"
        params["brand"] = brand
        
    sql += " ORDER BY pi.posting_date DESC, pi.name"
    
    data = frappe.db.sql(sql, params, as_dict=True)

    # Track distinct items and vouchers
    total_items_set = set()
    total_vouchers_set = set()
    
    for d in data:
        total_items_set.add(d.item_code)
        total_vouchers_set.add(d.voucher_no)

    return data, len(total_items_set), len(total_vouchers_set)

def get_summary(data, items_count, vouchers_count):
    total_costs = sum(flt(d.get("amount")) for d in data)
    
    return [
        {"value": total_costs, "indicator": "red", "label": _("Total Costs"), "datatype": "Currency"},
        {"value": items_count, "indicator": "blue", "label": _("Items"), "datatype": "Int"},
        {"value": vouchers_count, "indicator": "orange", "label": _("Vouchers"), "datatype": "Int"}
    ]
