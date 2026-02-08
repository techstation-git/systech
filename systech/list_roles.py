import frappe

def list_roles():
    roles = frappe.get_all("Role", pluck="name")
    print("System Roles:")
    for r in sorted(roles):
        print(f"- {r}")

if __name__ == "__main__":
    list_roles()
