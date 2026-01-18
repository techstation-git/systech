import frappe
import json

def get_meta():
    try:
        # Check if Monthly Distribution exists
        if not frappe.db.exists("DocType", "Monthly Distribution"):
            print("Monthly Distribution DocType not found")
            return

        meta = frappe.get_meta("Monthly Distribution")
        fields = [f.fieldname for f in meta.fields]
        print(f"Fields: {fields}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    frappe.connect("systech") # Try default site or systech
    get_meta()
