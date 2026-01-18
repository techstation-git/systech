import frappe
from frappe import _
from frappe.utils import flt


@frappe.whitelist()
def get_dashboard_data():
    """
    Get sales manager dashboard data
    Only accessible to Sales Manager role
    """
    # Check if user has Sales Manager role
    if "Sales Manager" not in frappe.get_roles():
        frappe.throw(_("Access Denied: This dashboard is only accessible to Sales Managers"))
    
    data = {
        "stats": get_stats(),
        "orders": get_recent_orders(),
        "stock": get_stock_overview()
    }
    
    return data


def get_stats():
    """Get dashboard statistics"""
    # Total orders
    total_orders = frappe.db.count('Sales Order')
    
    # Pending orders
    pending_orders = frappe.db.count('Sales Order', {
        'status': ['in', ['Draft', 'To Deliver and Bill', 'To Bill']]
    })
    
    # Total revenue from submitted sales orders
    revenue_data = frappe.db.sql("""
        SELECT SUM(grand_total) as total, currency
        FROM `tabSales Order`
        WHERE docstatus = 1
        GROUP BY currency
        ORDER BY total DESC
        LIMIT 1
    """, as_dict=True)
    
    total_revenue = revenue_data[0].total if revenue_data else 0
    currency = revenue_data[0].currency if revenue_data else frappe.defaults.get_global_default('currency')
    
    # Total stock value
    stock_value = frappe.db.sql("""
        SELECT SUM(actual_qty * valuation_rate) as total_value
        FROM `tabBin`
        WHERE actual_qty > 0
    """, as_dict=True)
    
    total_stock_value = stock_value[0].total_value if stock_value and stock_value[0].total_value else 0
    
    return {
        "total_orders": total_orders,
        "pending_orders": pending_orders,
        "total_revenue": total_revenue,
        "currency": currency,
        "total_stock_value": total_stock_value
    }


def get_recent_orders():
    """Get recent sales orders"""
    orders = frappe.db.sql("""
        SELECT 
            name,
            customer,
            transaction_date,
            total_qty,
            base_net_total,
            grand_total,
            currency,
            status
        FROM `tabSales Order`
        ORDER BY creation DESC
        LIMIT 20
    """, as_dict=True)
    
    return orders


def get_stock_overview():
    """Get stock overview with item details"""
    stock = frappe.db.sql("""
        SELECT 
            b.item_code,
            i.item_name,
            b.warehouse,
            b.actual_qty,
            b.valuation_rate,
            (b.actual_qty * b.valuation_rate) as total_value
        FROM `tabBin` b
        LEFT JOIN `tabItem` i ON b.item_code = i.item_code
        WHERE b.actual_qty > 0
        ORDER BY total_value DESC
        LIMIT 20
    """, as_dict=True)
    
    return stock


@frappe.whitelist()
def get_salesperson_dashboard_data():
    """
    Get salesperson dashboard data for current month
    Shows only data linked to the logged-in salesperson
    """
    from frappe.utils import get_first_day, get_last_day, today
    
    current_month_start = get_first_day(today())
    current_month_end = get_last_day(today())
    
    # Get salesperson linked to current user
    salesperson = get_current_salesperson()
    
    # Fetch Locked Items Details (Strictly no prices)
    # We use the same permissions logic from get_salesperson_stats
    condition = ""
    query_values = {'start_date': current_month_start, 'end_date': current_month_end}
    if salesperson:
        condition = "st.sales_person = %(salesperson)s"
        query_values['salesperson'] = salesperson
    else:
        condition = "so.owner = %(user)s"
        query_values['user'] = frappe.session.user

    locked_items_details = frappe.db.sql(f"""
        SELECT 
            so.name, 
            so.customer_name as customer, 
            so.total_qty as qty, 
            so.transaction_date as date
        FROM `tabSales Order` so
        LEFT JOIN `tabSales Team` st ON st.parent = so.name AND st.parenttype = 'Sales Order'
        WHERE ({condition})
        AND so.workflow_state = 'Locked'
        AND so.docstatus < 2
        ORDER BY so.creation DESC
    """, query_values, as_dict=True)

    data = {
        "stats": get_salesperson_stats(salesperson, current_month_start, current_month_end),
        "salesperson": salesperson,
        "category_stock": get_stock_summary_by_item_group(),
        "locked_items_details": locked_items_details,
        "period": {
            "start": current_month_start,
            "end": current_month_end
        }
    }
    
    return data


def get_current_salesperson():
    """Get the Sales Person linked to the current logged-in user"""
    current_user = frappe.session.user
    salesperson = None
    
    # 1. Try via Employee link (standard ERPNext)
    employee = frappe.db.get_value("Employee", {"user_id": current_user}, "name")
    if employee:
        salesperson = frappe.db.get_value('Sales Person', {'employee': employee}, 'name')
    
    # 2. If not found, try to match by name
    if not salesperson:
        user_full_name = frappe.get_value('User', current_user, 'full_name')
        if user_full_name:
            salesperson = frappe.db.get_value('Sales Person', 
                {'sales_person_name': user_full_name}, 
                'name'
            )
            
    return salesperson



def auto_assign_sales_person(doc, method):
    """
    Auto-assign the current logged-in user as a Sales Person to the document.
    Hooked to: Sales Order, Sales Invoice, Quotation (before_insert)
    """
    salesperson = get_current_salesperson()
    if not salesperson:
        return

    # Check if sales_team table exists in doc
    if not hasattr(doc, 'sales_team'):
        return

    # Check if salesperson is already in the team
    for entry in doc.sales_team:
        if entry.sales_person == salesperson:
            return

    # Calculate Commission Rate based on Target
    commission_rate = 0
    
    # 1. Get Sales Person Details (Target & Incentive Rate)
    sp_details = frappe.db.get_value('Sales Person', salesperson, 
        ['incentive_rate', 'commission_rate'], as_dict=True)
    
    if sp_details:
        # Standard rate
        commission_rate = sp_details.commission_rate or 0
        
        # Check if Incentive applies (if incentive_rate is set)
        if sp_details.get('incentive_rate'):
            from frappe.utils import get_first_day, get_last_day, today
            
            start_date = get_first_day(today())
            end_date = get_last_day(today())
            
            # Fetch stats
            stats = get_salesperson_stats(salesperson, start_date, end_date)
            
            current_sales = stats.get('total_sales', 0)
            current_qty = stats.get('total_items', 0)
            
            target_amount = stats.get('sales_target', 0)
            target_qty = stats.get('target_qty', 0)
            
            # Use strictly AND logic if both are present
            # If only one is present, use that one.
            
            is_target_met = False
            
            if target_amount > 0 and target_qty > 0:
                # Both targets must be met
                if current_sales >= target_amount and current_qty >= target_qty:
                    is_target_met = True
            elif target_amount > 0:
                # Only Amount target
                if current_sales >= target_amount:
                    is_target_met = True
            elif target_qty > 0:
                # Only Qty target
                if current_qty >= target_qty:
                    is_target_met = True
            
            if is_target_met:
                 # Additive: Standard Commission + Incentive Rate
                 commission_rate = flt(sp_details.commission_rate) + flt(sp_details.incentive_rate)

    # Add salesperson to team
    contribution = 100 if not doc.sales_team else 0
    
    doc.append('sales_team', {
        'sales_person': salesperson,
        'allocated_percentage': contribution,
        'commission_rate': commission_rate,
        'incentives': 0 # Standard field, can be calculated
    })


def get_stock_summary_by_item_group():
    """Get stock summary grouped by Item Group"""
    data = frappe.db.sql("""
        SELECT 
            i.item_group as group_name,
            COUNT(DISTINCT i.name) as total_items,
            SUM(b.actual_qty) as total_qty,
            SUM(b.actual_qty * b.valuation_rate) as total_value,
            b.stock_uom
        FROM `tabBin` b
        JOIN `tabItem` i ON b.item_code = i.item_code
        WHERE b.actual_qty > 0 AND i.item_group IS NOT NULL AND i.item_group != ''
        GROUP BY i.item_group
        ORDER BY total_value DESC
    """, as_dict=True)
    
    return data



@frappe.whitelist()
def get_salesperson_stats(salesperson, start_date, end_date):
    """Get statistics for a specific salesperson for the given period"""
    from frappe.utils import flt, getdate
    
    stats = {
        "orders": 0,
        "invoices": 0,
        "total_sales": 0,
        "total_items": 0,
        "sales_target": 0,
        "target_qty": 0,
        "locked_items": 0,
        "currency": frappe.defaults.get_global_default('currency') or 'USD'
    }

    # Determine Filter Condition
    # If we are looking up a specific salesperson, restrict STRICTLY to that salesperson
    # If no salesperson is linked, show data owned by the current session user (Personal Dashboard fallback)
    condition = ""
    query_values = {
        'start_date': start_date, 
        'end_date': end_date
    }
    
    if salesperson:
        condition = "st.sales_person = %(salesperson)s"
        query_values['salesperson'] = salesperson
    else:
        condition = "so.owner = %(user)s"
        query_values['user'] = frappe.session.user

    
    # Get orders count for current month (Draft and Submitted)
    orders = frappe.db.sql(f"""
        SELECT COUNT(DISTINCT so.name) as count
        FROM `tabSales Order` so
        LEFT JOIN `tabSales Team` st ON st.parent = so.name AND st.parenttype = 'Sales Order'
        WHERE ({condition})
        AND so.transaction_date BETWEEN %(start_date)s AND %(end_date)s
        AND so.docstatus < 2
    """, query_values, as_dict=True)
    
    stats['orders'] = orders[0].count if orders else 0
    
    # Get invoices count for current month
    # Note: Sales Invoice also has Sales Team.
    # Adjust condition table alias if needed, but 'so' was used for owner check.
    # Ideally standard alias 'doc' or similar. 
    # But here we need to rebuild the condition for Invoice specifically if we used 'so' alias in condition.
    
    # Re-build condition for Invoice using 'si' alias
    if salesperson:
        inv_condition = "st.sales_person = %(salesperson)s"
    else:
        inv_condition = "si.owner = %(user)s"

    invoices = frappe.db.sql(f"""
        SELECT COUNT(DISTINCT si.name) as count
        FROM `tabSales Invoice` si
        LEFT JOIN `tabSales Team` st ON st.parent = si.name AND st.parenttype = 'Sales Invoice'
        WHERE ({inv_condition})
        AND si.posting_date BETWEEN %(start_date)s AND %(end_date)s
        AND si.docstatus = 1
    """, query_values, as_dict=True)
    
    stats['invoices'] = invoices[0].count if invoices else 0
    
    # Get total sales and items for current month (Sales Order)
    sales_data = frappe.db.sql(f"""
        SELECT 
            SUM(so.grand_total) as total_sales,
            SUM(so.total_qty) as total_items,
            so.currency
        FROM `tabSales Order` so
        LEFT JOIN `tabSales Team` st ON st.parent = so.name AND st.parenttype = 'Sales Order'
        WHERE ({condition})
        AND so.transaction_date BETWEEN %(start_date)s AND %(end_date)s
        AND so.docstatus = 1
        GROUP BY so.currency
        ORDER BY total_sales DESC
        LIMIT 1
    """, query_values, as_dict=True)
    
    if sales_data:
        stats['total_sales'] = flt(sales_data[0].total_sales)
        stats['total_items'] = flt(sales_data[0].total_items)
        stats['currency'] = sales_data[0].currency or stats['currency']
    


    # Get sales target: Look for Specific Month, OR Fallback to Empty Item Group (Generic Yearly Target)
    # Also fetch Distribution Percentage if available
    target_data = frappe.db.sql("""
        SELECT 
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
        AND (
            (MONTHNAME(%(start_date)s) = 'January' AND td.item_group = 'January')
            OR (MONTHNAME(%(start_date)s) = 'February' AND td.item_group = 'February')
            OR (MONTHNAME(%(start_date)s) = 'March' AND td.item_group = 'March')
            OR (MONTHNAME(%(start_date)s) = 'April' AND td.item_group = 'April')
            OR (MONTHNAME(%(start_date)s) = 'May' AND td.item_group = 'May')
            OR (MONTHNAME(%(start_date)s) = 'June' AND td.item_group = 'June')
            OR (MONTHNAME(%(start_date)s) = 'July' AND td.item_group = 'July')
            OR (MONTHNAME(%(start_date)s) = 'August' AND td.item_group = 'August')
            OR (MONTHNAME(%(start_date)s) = 'September' AND td.item_group = 'September')
            OR (MONTHNAME(%(start_date)s) = 'October' AND td.item_group = 'October')
            OR (MONTHNAME(%(start_date)s) = 'November' AND td.item_group = 'November')
            OR (MONTHNAME(%(start_date)s) = 'December' AND td.item_group = 'December')
            OR (td.item_group IS NULL OR td.item_group = '' OR td.item_group = 'All Item Groups') 
        )
        ORDER BY td.target_amount DESC
        LIMIT 1
    """, {
        'salesperson': salesperson,
        'start_date': start_date
    }, as_dict=True)
    
    if target_data:
        amount = flt(target_data[0].target_amount)
        qty = flt(target_data[0].target_qty)
        percentage = flt(target_data[0].percentage_allocation)
        
        # If distribution percentage exists, apply it
        if percentage > 0:
            amount = (amount * percentage) / 100.0
            qty = (qty * percentage) / 100.0
            
        stats['sales_target'] = amount
        stats['target_qty'] = qty
    
    # Get locked items count for current month (using workflow_state = 'Locked')
    locked_items = frappe.db.sql(f"""
        SELECT COUNT(*) as count
        FROM `tabSales Order` so
        LEFT JOIN `tabSales Team` st ON st.parent = so.name AND st.parenttype = 'Sales Order'
        WHERE ({condition})
        AND so.transaction_date BETWEEN %(start_date)s AND %(end_date)s
        AND so.workflow_state = 'Locked'
    """, query_values, as_dict=True)
    
    stats['locked_items'] = locked_items[0].count if locked_items else 0
    
    return stats
