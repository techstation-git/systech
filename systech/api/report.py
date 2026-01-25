import frappe

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_brands_for_supplier(doctype, txt, searchfield, start, page_len, filters):
    supplier = filters.get("supplier")
    if not supplier:
        return []
    
    # Brands (Item Groups) that this supplier has supplied in Purchase Invoices
    brands = frappe.db.sql("""
        SELECT DISTINCT item.item_group
        FROM `tabPurchase Invoice Item` pi_item
        JOIN `tabPurchase Invoice` pi ON pi_item.parent = pi.name
        JOIN `tabItem` item ON pi_item.item_code = item.name
        WHERE pi.supplier = %s
        AND pi.docstatus = 1
        AND item.item_group LIKE %s
        LIMIT %s, %s
    """, (supplier, f"%{txt}%", start, page_len))
    
    return brands

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_suppliers_for_brand(doctype, txt, searchfield, start, page_len, filters):
    brand = filters.get("brand")
    if not brand:
        return []
    
    # Suppliers who have supplied items in this Item Group (Brand)
    suppliers = frappe.db.sql("""
        SELECT DISTINCT pi.supplier
        FROM `tabPurchase Invoice Item` pi_item
        JOIN `tabPurchase Invoice` pi ON pi_item.parent = pi.name
        JOIN `tabItem` item ON pi_item.item_code = item.name
        WHERE item.item_group = %s
        AND pi.docstatus = 1
        AND pi.supplier LIKE %s
        LIMIT %s, %s
    """, (brand, f"%{txt}%", start, page_len))
    
    return suppliers
