
import sys
import os
import json
import pymysql
from datetime import datetime

# Locate site_config.json
bench_path = os.path.abspath(os.path.join(os.getcwd(), '..', '..'))
site_config_path = os.path.join(bench_path, 'sites', 'techstation.com', 'site_config.json')

try:
    with open(site_config_path, 'r') as f:
        conf = json.load(f)
    
    conn = pymysql.connect(
        host=conf.get('db_host', '127.0.0.1'),
        user=conf['db_name'],
        password=conf['db_password'],
        database=conf['db_name'],
        cursorclass=pymysql.cursors.DictCursor
    )
    
    with conn.cursor() as cursor:
        print("=== CHECKING HASSAN'S DATA ===\n")
        
        # 1. Check Hassan's Sales Person record
        print("1. SALES PERSON DETAILS:")
        cursor.execute("""
            SELECT name, sales_person_name, commission_rate, incentive_rate, employee 
            FROM `tabSales Person` 
            WHERE sales_person_name = 'Hassan'
        """)
        sp = cursor.fetchone()
        if sp:
            print(f"   Name: {sp['name']}")
            print(f"   Commission Rate: {sp['commission_rate']}%")
            print(f"   Incentive Rate: {sp['incentive_rate']}%")
            print(f"   Employee: {sp['employee']}\n")
        else:
            print("   NOT FOUND!\n")
            exit(1)
        
        # 2. Check Sales Orders
        print("2. SALES ORDERS:")
        cursor.execute("""
            SELECT 
                so.name, 
                so.transaction_date,
                so.docstatus,
                so.grand_total,
                so.total_qty,
                so.workflow_state
            FROM `tabSales Order` so
            WHERE MONTH(so.transaction_date) = MONTH(NOW())
            AND YEAR(so.transaction_date) = YEAR(NOW())
            ORDER BY so.creation DESC
        """)
        orders = cursor.fetchall()
        print(f"   Total orders this month: {len(orders)}")
        for o in orders[:5]:  # Show first 5
            print(f"   - {o['name']}: Status={o['docstatus']}, Workflow={o['workflow_state']}, Total={o['grand_total']}, Qty={o['total_qty']}")
        
        # 3. Check Sales Team for Hassan
        print("\n3. HASSAN IN SALES TEAM:")
        cursor.execute("""
            SELECT 
                st.parent, 
                st.sales_person,
                st.allocated_percentage,
                st.commission_rate,
                so.docstatus,
                so.grand_total,
                so.total_qty
            FROM `tabSales Team` st
            INNER JOIN `tabSales Order` so ON so.name = st.parent
            WHERE st.parenttype = 'Sales Order'
            AND st.sales_person = 'Hassan'
            AND MONTH(so.transaction_date) = MONTH(NOW())
            AND YEAR(so.transaction_date) = YEAR(NOW())
        """)
        team_orders = cursor.fetchall()
        print(f"   Orders with Hassan in Sales Team: {len(team_orders)}")
        total_sales = 0
        total_qty = 0
        for t in team_orders:
            print(f"   - {t['parent']}: DocStatus={t['docstatus']}, Total={t['grand_total']}, Qty={t['total_qty']}, Commission={t['commission_rate']}%")
            if t['docstatus'] == 1:  # Submitted
                total_sales += float(t['grand_total'])
                total_qty += float(t['total_qty'])
        
        print(f"\n   CALCULATED STATS (Submitted Only):")
        print(f"   Total Sales: {total_sales}")
        print(f"   Total Qty: {total_qty}")
        
        # 4. Check Targets
        print("\n4. HASSAN'S TARGETS:")
        cursor.execute("""
            SELECT 
                td.item_group,
                td.target_amount, 
                td.target_qty,
                td.distribution_id,
                mdp.percentage_allocation
            FROM `tabTarget Detail` td
            LEFT JOIN `tabMonthly Distribution Percentage` mdp 
                ON mdp.parent = td.distribution_id 
                AND mdp.month = MONTHNAME(NOW())
            WHERE td.parent = 'Hassan'
            AND td.parenttype = 'Sales Person'
            AND td.fiscal_year = YEAR(NOW())
        """)
        targets = cursor.fetchall()
        if targets:
            for t in targets:
                print(f"   Group: {t['item_group']}, Amount: {t['target_amount']}, Qty: {t['target_qty']}, Distribution: {t['distribution_id']}, Allocation: {t['percentage_allocation']}%")
                
                amt = float(t['target_amount'] or 0)
                qty = float(t['target_qty'] or 0)
                pct = float(t['percentage_allocation'] or 0)
                
                if pct > 0:
                    amt = (amt * pct) / 100
                    qty = (qty * pct) / 100
                
                print(f"   -> Effective Monthly Target: Amount={amt}, Qty={qty}")
                
                # Check if met
                amt_met = total_sales >= amt if amt > 0 else False
                qty_met = total_qty >= qty if qty > 0 else False
                
                if amt > 0 and qty > 0:
                    target_met = amt_met and qty_met
                elif amt > 0:
                    target_met = amt_met
                elif qty > 0:
                    target_met = qty_met
                else:
                    target_met = False
                
                print(f"   -> Target Met? {target_met}")
                applicable_rate = sp['incentive_rate'] if target_met else sp['commission_rate']
                print(f"   -> Applicable Rate: {applicable_rate}%")
        else:
            print("   NO TARGETS SET")

except Exception as e:
    import traceback
    traceback.print_exc()
finally:
    if 'conn' in locals() and conn.open: conn.close()
