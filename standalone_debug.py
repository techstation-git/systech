
import sys
import os
import logging

# Move up two levels from apps/systech
bench_path = os.path.abspath(os.path.join(os.getcwd(), '..', '..'))
os.chdir(bench_path)

sys.path.append(os.path.join(bench_path, 'apps', 'frappe'))
sys.path.append(os.path.join(bench_path, 'apps', 'erpnext'))
sys.path.append(os.path.join(bench_path, 'apps', 'systech'))

import frappe
from frappe.utils import get_first_day, get_last_day, today
from systech.services.api import get_salesperson_stats

# MOCK LOGGER
def mock_logger(log_name, *args, **kwargs):
    return logging.getLogger(log_name)
frappe.logger = mock_logger

def debug():
    try:
        print("Initializing Frappe...")
        frappe.init(site='techstation.com')
        print("Connecting to DB...")
        frappe.connect()

        # Check sales person
        sp = frappe.db.get_value('Sales Person', {'sales_person_name': 'Mohammed'}, ['name', 'commission_rate', 'incentive_rate'], as_dict=True)
        if not sp:
             l = frappe.get_list('Sales Person', filters={'sales_person_name': ['like', '%Mohammed%']})
             if l: 
                 sp = frappe.db.get_value('Sales Person', l[0].name, ['name', 'commission_rate', 'incentive_rate'], as_dict=True)
        
        if not sp:
            print("Sales Person Mohammed not found. Active Sales People:")
            pp = frappe.get_list('Sales Person', fields=['sales_person_name'])
            for p in pp: print(p.sales_person_name)
            return

        print(f"Sales Person: {sp.name}")
        print(f"Commission Rate: {sp.commission_rate}, Incentive Rate: {sp.incentive_rate}")
        
        start = get_first_day(today())
        end = get_last_day(today())
        print(f"Stats Period: {start} to {end}")
        
        stats = get_salesperson_stats(sp.name, start, end)
        print("\n--- STATS ---")
        print(stats)

        print("\n--- RAW TARGET ROWS ---")
        target_data = frappe.db.sql("""
            SELECT 
                td.name,
                td.item_group,
                td.target_amount, 
                td.target_qty,
                td.distribution_id,
                mdp.percentage_allocation
            FROM `tabTarget Detail` td
            LEFT JOIN `tabMonthly Distribution Percentage` mdp 
                ON mdp.parent = td.distribution_id 
                AND mdp.month = MONTHNAME(%s)
            WHERE td.parent = %s
            AND td.parenttype = 'Sales Person'
            AND td.fiscal_year = YEAR(%s)
        """, (start, sp.name, start), as_dict=True)
        
        for row in target_data:
            print(row)

    except Exception as e:
        import traceback
        traceback.print_exc()
    finally:
        if frappe.db: frappe.destroy()

if __name__ == "__main__":
    debug()
