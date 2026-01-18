
import sys
import os
import json
import pymysql

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
        print("Connected.")
        
        # 1. Find User 'Hassan'
        print("--- User ---")
        cursor.execute("SELECT name, email, first_name, last_name, full_name, role_profile_name FROM `tabUser` WHERE first_name LIKE '%Hassan%' OR email LIKE '%Hassan%'")
        users = cursor.fetchall()
        for u in users:
            print(u)
            
            # 2. Check Employee Link
            print("  --- Linked Employee ---")
            cursor.execute("SELECT name, employee_name, user_id FROM `tabEmployee` WHERE user_id = %s", (u['name'],))
            employees = cursor.fetchall()
            for e in employees:
                print(f"  {e}")
                
                # 3. Check Sales Person Link via Employee
                print("    --- Linked Sales Person (by Employee) ---")
                cursor.execute("SELECT name, sales_person_name, employee FROM `tabSales Person` WHERE employee = %s", (e['name'],))
                sps = cursor.fetchall()
                for s in sps:
                    print(f"    {s}")

        # 4. Check Sales Person by Name (Fallback)
        print("--- Sales Person (by Name 'Hassan') ---")
        cursor.execute("SELECT name, sales_person_name, employee FROM `tabSales Person` WHERE sales_person_name LIKE '%Hassan%'")
        for s in cursor.fetchall():
            print(s)

except Exception as e:
    import traceback
    traceback.print_exc()
finally:
    if 'conn' in locals() and conn.open: conn.close()
