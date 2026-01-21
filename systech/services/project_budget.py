import frappe
from frappe import _
from frappe.utils import flt

def validate_project_budget(doc, method):
    """
    Validate that the sum of sub-projects budget does not exceed the parent project's budget.
    Hooked to: Project.validate
    """
    # 1. Check if Parent Project exists
    if not doc.parent_project:
        return

    parent_project = frappe.get_doc("Project", doc.parent_project)
    
    # 2. Get Parent Budget
    parent_budget = flt(parent_project.estimated_costing)
    if parent_budget <= 0:
        # If parent has no budget, we might want to allow or block. 
        # User requirement: "Parent project it can have the budget". 
        # Usually implies if parent has budget, respect it. If 0, maybe unlimited? 
        # Let's assume strict control if set. If 0, warn? 
        # Requirement says "its sub projects budgets sum should not exceed the parent project budget".
        # If parent is 0, then sub-projects cannot have budget > 0.
        pass

    # 3. Calculate sum of ALL sub-projects (including current one)
    # We need to exclude the current doc from DB if it exists (update scenario) 
    # and add the new value from the doc instance.
    
    sub_projects = frappe.db.sql("""
        SELECT name, estimated_costing 
        FROM `tabProject` 
        WHERE parent_project = %s AND name != %s
    """, (doc.parent_project, doc.name), as_dict=True)

    current_sub_projects_total = sum(flt(p.estimated_costing) for p in sub_projects)
    
    new_total = current_sub_projects_total + flt(doc.estimated_costing)

    # 4. Compare
    if new_total > parent_budget:
        frappe.throw(_("Total budget of sub-projects ({0}) exceeds Parent Project budget ({1}). Available: {2}").format(
            frappe.format_value(new_total, dict(fieldtype='Currency')),
            frappe.format_value(parent_budget, dict(fieldtype='Currency')),
            frappe.format_value(parent_budget - current_sub_projects_total, dict(fieldtype='Currency'))
        ))
