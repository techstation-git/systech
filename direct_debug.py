
import sys
import os
import json
import pymysql

# Locate site_config.json
bench_path = os.path.abspath(os.path.join(os.getcwd(), '..', '..'))
site_config_path = os.path.join(bench_path, 'sites', 'techstation.com', 'site_config.json')

print(f"Reading config from: {site_config_path}")

try:
    with open(site_config_path, 'r') as f:
        conf = json.load(f)
    
    # Connect
    conn = pymysql.connect(
        host=conf.get('db_host', '127.0.0.1'),
        user=conf['db_name'],
        password=conf['db_password'],
        database=conf['db_name'],
        cursorclass=pymysql.cursors.DictCursor
    )
    
    with conn.cursor() as cursor:
        print("Connected to DB successfully!")
        
        # 1. Find Mohammed
        print("Searching for Mohammed...")
        cursor.execute("SELECT name, sales_person_name, commission_rate, incentive_rate FROM `tabSales Person` WHERE sales_person_name LIKE '%Mohammed%'")
        sp_rows = cursor.fetchall()
        
        if not sp_rows:
            print("Mohammed not found. Active Sales People:")
            cursor.execute("SELECT sales_person_name FROM `tabSales Person` LIMIT 10")
            for r in cursor.fetchall(): print(f" - {r['sales_person_name']}")
        
        for sp in sp_rows:
            print(f"\n--- Analysis for {sp['sales_person_name']} ({sp['name']}) ---")
            print(f"Standard Rate: {sp['commission_rate']}%, Incentive Rate: {sp['incentive_rate']}%")
            
            # 2. Get Targets for Current Month/Year
            print("Fetching Targets...")
            # We want to emulate month name logic
            cursor.execute("SELECT MONTHNAME(NOW()) as m_name, YEAR(NOW()) as year")
            date_info = cursor.fetchone()
            curr_month = date_info['m_name']
            curr_year = date_info['year']
            print(f"Current Period: {curr_month} {curr_year}")
            
            cursor.execute("""
                SELECT 
                    td.target_amount, td.target_qty, td.item_group, td.distribution_id,
                    mdp.percentage_allocation
                FROM `tabTarget Detail` td
                LEFT JOIN `tabMonthly Distribution Percentage` mdp 
                    ON mdp.parent = td.distribution_id 
                    AND mdp.month = %s
                WHERE td.parent = %s
                AND td.parenttype = 'Sales Person'
                AND td.fiscal_year = %s
            """, (curr_month, sp['name'], curr_year))
            
            targets = cursor.fetchall()
            effective_target_amt = 0
            effective_target_qty = 0
            
            for t in targets:
                print(f"Target Row: Group='{t['item_group']}', Amount={t['target_amount']}, Qty={t['target_qty']}, DistID={t['distribution_id']}, Alloc={t['percentage_allocation']}%")
                
                # Logic replication
                amt = float(t['target_amount'])
                qty = float(t['target_qty'])
                pct = float(t['percentage_allocation'] or 0)
                
                if pct > 0:
                    amt = (amt * pct) / 100.0
                    qty = (qty * pct) / 100.0
                
                # We essentially take the first matching one in real logic, but let's sum or show max to understand
                if amt > effective_target_amt: effective_target_amt = amt
                if qty > effective_target_qty: effective_target_qty = qty

            print(f"Effective Monthly Target: Amount={effective_target_amt}, Qty={effective_target_qty}")
            
            # 3. Get Actual Sales Stats
            print("Fetching Actual Sales...")
            cursor.execute("""
                SELECT 
                    COUNT(DISTINCT so.name) as order_count,
                    SUM(so.grand_total) as total_sales, 
                    SUM(so.total_qty) as total_qty
                FROM `tabSales Order` so
                LEFT JOIN `tabSales Team` st ON st.parent = so.name
                WHERE (st.sales_person = %s)
                AND MONTH(so.transaction_date) = MONTH(NOW())
                AND YEAR(so.transaction_date) = YEAR(NOW())
                AND so.docstatus = 1
            """, (sp['name'],))
            stats = cursor.fetchone()
            
            actual_sales = float(stats['total_sales'] or 0)
            actual_qty = float(stats['total_qty'] or 0)
            print(f"Actuals: Sales={actual_sales}, Qty={actual_qty}")
            
            # 4. Conclusion
            print("--- CONCLUSION ---")
            is_met = False
            if effective_target_amt > 0 and effective_target_qty > 0:
                if actual_sales >= effective_target_amt and actual_qty >= effective_target_qty: is_met = True
            elif effective_target_amt > 0:
                if actual_sales >= effective_target_amt: is_met = True
            elif effective_target_qty > 0:
                if actual_qty >= effective_target_qty: is_met = True
                
            print(f"Target Met? {is_met}")
            print(f"Applied Rate: {sp['incentive_rate'] if is_met else sp['commission_rate']}%")

except Exception as e:
    import traceback
    traceback.print_exc()
finally:
    if 'conn' in locals() and conn.open: conn.close()
