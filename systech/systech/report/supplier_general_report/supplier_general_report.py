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
        {"label": _("Brand (Item Group)"), "fieldname": "item_group", "fieldtype": "Link", "options": "Item Group", "width": 160},
        {"label": _("Total Costs"), "fieldname": "costs", "fieldtype": "Currency", "width": 130},
        {"label": _("Total Paid"), "fieldname": "paid_amount", "fieldtype": "Currency", "width": 130},
        {"label": _("Outstanding Amount"), "fieldname": "outstanding", "fieldtype": "Currency", "width": 130}
    ]

def get_data(filters):
    supplier = filters.get("supplier")
    brand = filters.get("brand") # Item Group
    from_date = filters.get("from_date")
    to_date = filters.get("to_date")
    
    date_condition = ""
    params = {}
    if from_date and to_date:
        date_condition = "AND pi.posting_date BETWEEN %(from_date)s AND %(to_date)s"
        params["from_date"] = from_date
        params["to_date"] = to_date

    # Query Purchase Invoices joined with Items to get Item Group
    sql = f"""
        SELECT 
            pi.supplier,
            pi.name as pi_name,
            item.item_group,
            si_item.item_code,
            SUM(si_item.base_amount) as costs,
            SUM(pi.base_paid_amount * (si_item.base_amount / NULLIF(pi.base_grand_total, 0))) as paid_amount,
            SUM((pi.base_grand_total - pi.base_paid_amount) * (si_item.base_amount / NULLIF(pi.base_grand_total, 0))) as outstanding
        FROM `tabPurchase Invoice Item` si_item
        JOIN `tabPurchase Invoice` pi ON si_item.parent = pi.name
        JOIN `tabItem` item ON si_item.item_code = item.name
        WHERE pi.docstatus = 1
        {date_condition}
    """
    params = {}
    if supplier:
        sql += " AND pi.supplier = %(supplier)s"
        params["supplier"] = supplier
    if brand:
        sql += " AND item.item_group = %(brand)s"
        params["brand"] = brand
        
    sql += " GROUP BY pi.supplier, item.item_group ORDER BY pi.supplier, item.item_group"
    
    data = frappe.db.sql(sql, params, as_dict=True)

    # Track distinct items and vouchers
    total_items_set = set()
    total_vouchers_set = set()
    
    # We need to re-query for accurate counts if grouped
    vouchers = frappe.get_all("Purchase Invoice", filters={"docstatus": 1, "posting_date": ["between", [from_date, to_date]] if from_date else ["!=", ""]})
    if supplier: vouchers = [v for v in vouchers if v.supplier == supplier]
    for v in vouchers: total_vouchers_set.add(v.name)
    
    items = frappe.get_all("Purchase Invoice Item", filters={"parent": ["in", list(total_vouchers_set)] if total_vouchers_set else ["!=", ""]}, fields=["item_code"])
    for itm in items: total_items_set.add(itm.item_code)

    return data, len(total_items_set), len(total_vouchers_set)

def get_summary(data, items_count, vouchers_count):
    total_costs = sum(flt(d.get("costs")) for d in data)
    total_paid = sum(flt(d.get("paid_amount")) for d in data)
    
    return [
        {"value": total_costs, "indicator": "red", "label": _("Total Costs"), "datatype": "Currency"},
        {"value": items_count, "indicator": "blue", "label": _("Items"), "datatype": "Int"},
        {"value": vouchers_count, "indicator": "orange", "label": _("Vouchers"), "datatype": "Int"},
        {"value": total_paid, "indicator": "green", "label": _("Total Paid"), "datatype": "Currency"}
    ]
