import frappe
from frappe import _


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
    
    data = {
        "stats": get_salesperson_stats(salesperson, current_month_start, current_month_end),
        "salesperson": salesperson,
        "category_stock": get_stock_summary_by_item_group(),
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
            # Update commission rate if logic requires checking target again (optional)
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
            
            # Use Total Sales (Actual + This New Order)
            current_sales = stats.get('total_sales', 0)
            target = stats.get('sales_target', 0)
            
            # If (Current Sales + New Doc Grand Total) > Target, apply Incentive Rate
            # Note: For creation, we assume if they are ALREADY over target, or if this pushes them over.
            # A simpler policy: If they have met the target, they get the higher rate.
            
            if target > 0 and current_sales >= target:
                 commission_rate = sp_details.incentive_rate

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


def get_salesperson_stats(salesperson, start_date, end_date):
    """Get statistics for a specific salesperson for the given period"""
    from frappe.utils import flt
    
    stats = {
        "orders": 0,
        "invoices": 0,
        "total_sales": 0,
        "total_items": 0,
        "sales_target": 0,
        "locked_items": 0,
        "currency": frappe.defaults.get_global_default('currency') or 'USD'
    }
    
    # Even if no salesperson found, we still query for docs owned by the user
    
    # Get orders count for current month (Draft and Submitted)
    orders = frappe.db.sql("""
        SELECT COUNT(DISTINCT so.name) as count
        FROM `tabSales Order` so
        LEFT JOIN `tabSales Team` st ON st.parent = so.name AND st.parenttype = 'Sales Order'
        WHERE (so.owner = %(user)s OR st.sales_person = %(salesperson)s)
        AND so.transaction_date BETWEEN %(start_date)s AND %(end_date)s
        AND so.docstatus < 2
    """, {
        'user': frappe.session.user,
        'salesperson': salesperson,
        'start_date': start_date,
        'end_date': end_date
    }, as_dict=True)
    
    stats['orders'] = orders[0].count if orders else 0
    
    # Get invoices count for current month
    invoices = frappe.db.sql("""
        SELECT COUNT(DISTINCT si.name) as count
        FROM `tabSales Invoice` si
        LEFT JOIN `tabSales Team` st ON st.parent = si.name AND st.parenttype = 'Sales Invoice'
        WHERE (si.owner = %(user)s OR st.sales_person = %(salesperson)s)
        AND si.posting_date BETWEEN %(start_date)s AND %(end_date)s
        AND si.docstatus = 1
    """, {
        'user': frappe.session.user,
        'salesperson': salesperson,
        'start_date': start_date,
        'end_date': end_date
    }, as_dict=True)
    
    stats['invoices'] = invoices[0].count if invoices else 0
    
    # Get total sales and items for current month
    sales_data = frappe.db.sql("""
        SELECT 
            SUM(so.grand_total) as total_sales,
            SUM(so.total_qty) as total_items,
            so.currency
        FROM `tabSales Order` so
        LEFT JOIN `tabSales Team` st ON st.parent = so.name AND st.parenttype = 'Sales Order'
        WHERE (so.owner = %(user)s OR st.sales_person = %(salesperson)s)
        AND so.transaction_date BETWEEN %(start_date)s AND %(end_date)s
        AND so.docstatus = 1
        GROUP BY so.currency
        ORDER BY total_sales DESC
        LIMIT 1
    """, {
        'user': frappe.session.user,
        'salesperson': salesperson,
        'start_date': start_date,
        'end_date': end_date
    }, as_dict=True)
    
    if sales_data:
        stats['total_sales'] = flt(sales_data[0].total_sales)
        stats['total_items'] = flt(sales_data[0].total_items)
        stats['currency'] = sales_data[0].currency or stats['currency']
    
    # Get sales target for current month
    from frappe.utils import get_first_day, get_last_day, getdate
    
    target_data = frappe.db.sql("""
        SELECT target_amount
        FROM `tabTarget Detail`
        WHERE parent = %(salesperson)s
        AND parenttype = 'Sales Person'
        AND fiscal_year = YEAR(%(start_date)s)
        AND (
            (MONTHNAME(%(start_date)s) = 'January' AND item_group = 'January')
            OR (MONTHNAME(%(start_date)s) = 'February' AND item_group = 'February')
            OR (MONTHNAME(%(start_date)s) = 'March' AND item_group = 'March')
            OR (MONTHNAME(%(start_date)s) = 'April' AND item_group = 'April')
            OR (MONTHNAME(%(start_date)s) = 'May' AND item_group = 'May')
            OR (MONTHNAME(%(start_date)s) = 'June' AND item_group = 'June')
            OR (MONTHNAME(%(start_date)s) = 'July' AND item_group = 'July')
            OR (MONTHNAME(%(start_date)s) = 'August' AND item_group = 'August')
            OR (MONTHNAME(%(start_date)s) = 'September' AND item_group = 'September')
            OR (MONTHNAME(%(start_date)s) = 'October' AND item_group = 'October')
            OR (MONTHNAME(%(start_date)s) = 'November' AND item_group = 'November')
            OR (MONTHNAME(%(start_date)s) = 'December' AND item_group = 'December')
        )
        LIMIT 1
    """, {
        'salesperson': salesperson,
        'start_date': start_date
    }, as_dict=True)
    
    if target_data:
        stats['sales_target'] = flt(target_data[0].target_amount)
    
    # Get locked items count for current month (using workflow_state = 'Locked')
    locked_items = frappe.db.sql("""
        SELECT COUNT(*) as count
        FROM `tabSales Order` so
        LEFT JOIN `tabSales Team` st ON st.parent = so.name AND st.parenttype = 'Sales Order'
        WHERE (so.owner = %(user)s OR st.sales_person = %(salesperson)s)
        AND so.transaction_date BETWEEN %(start_date)s AND %(end_date)s
        AND so.workflow_state = 'Locked'
    """, {
        'user': frappe.session.user,
        'salesperson': salesperson,
        'start_date': start_date,
        'end_date': end_date
    }, as_dict=True)
    
    stats['locked_items'] = locked_items[0].count if locked_items else 0
    
    return stats
