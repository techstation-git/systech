
import sys
import os

# Set up bench path
bench_path = os.path.abspath(os.path.join(os.getcwd(), '..', '..'))
os.chdir(bench_path)
sys.path.append(os.path.join(bench_path, 'apps', 'frappe'))

import frappe

def set_hassan_permission():
    try:
        frappe.init(site="techstation.com")
        frappe.connect()
        
        user = "hassan@gmail.com"
        allow = "Sales Person"
        value = "Hassan" # The Sales Person Name
        
        # 1. Check if user exists
        if not frappe.db.exists("User", user):
            print(f"User {user} not found")
            return

        # 2. Check if Sales Person exists
        if not frappe.db.exists(allow, value):
            print(f"{allow} {value} not found")
            return

        # 3. Create User Permission
        exists = frappe.db.exists("User Permission", {
            "user": user,
            "allow": allow,
            "for_value": value
        })
        
        if exists:
            print(f"User Permission already exists.")
        else:
            doc = frappe.get_doc({
                "doctype": "User Permission",
                "user": user,
                "allow": allow,
                "for_value": value,
                "is_default": 1
            })
            doc.insert(ignore_permissions=True)
            print(f"SUCCESS: Created User Permission limiting {user} to {allow}: {value}")
            
    finally:
        if frappe.db: frappe.destroy()

if __name__ == "__main__":
    set_hassan_permission()
