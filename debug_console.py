
# Import necessary modules
import frappe
from systech.services.api import get_salesperson_stats
from frappe.utils import get_first_day, get_last_day, today

def debug_mohammed():
    # 1. Find Mohammed
    salespersons = frappe.db.get_list('Sales Person', filters={'sales_person_name': ['like', '%Mohammed%']}, field_order='name')
    if not salespersons:
        print("Could not find any Sales Person with name like 'Mohammed'")
        return

    sp_name = salespersons[0].name
    print(f"DEBUGGING Sales Person: {sp_name}")

    # 2. Get Stats
    start = get_first_day(today())
    end = get_last_day(today())
    print(f"Period: {start} to {end}")
    
    stats = get_salesperson_stats(sp_name, start, end)
    print("\n--- STATS RETURNED ---")
    print(stats)
    
    # 3. Inspect Raw Target Data to show WHY
    print("\n--- RAW TARGET DATA ---")
    
    # Run the same query manualy to show the breakdown
    target_data = frappe.db.sql("""
        SELECT 
            td.item_group,
            td.target_amount, 
            td.target_qty,
            td.distribution_id,
            mdp.percentage_allocation
        FROM `tabTarget Detail` td
        LEFT JOIN `tabMonthly Distribution Percentage` mdp 
            ON mdp.parent = td.distribution_id 
            AND mdp.month = MONTHNAME(%(start_date)s)
        WHERE td.parent = %(salesperson)s
        AND td.parenttype = 'Sales Person'
        AND td.fiscal_year = YEAR(%(start_date)s)
    """, {
        'salesperson': sp_name,
        'start_date': start
    }, as_dict=True)
    
    for t in target_data:
        print(f"Row: Group='{t.item_group}', Amount={t.target_amount}, Qty={t.target_qty}, Distribution={t.distribution_id}, Alloc%={t.percentage_allocation}")

# Execute
debug_mohammed()
