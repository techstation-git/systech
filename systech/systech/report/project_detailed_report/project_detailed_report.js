frappe.query_reports["Project Detailed Report"] = {
    "filters": [
        {
            "fieldname": "timespan",
            "label": __("Range"),
            "fieldtype": "Select",
            "options": "Monthly\nYearly\nCustom",
            "default": "Monthly",
            "reqd": 1,
            "on_change": function () {
                let timespan = frappe.query_report.get_filter_value('timespan');
                if (timespan === 'Monthly') {
                    frappe.query_report.set_filter_value('from_date', frappe.datetime.month_start());
                    frappe.query_report.set_filter_value('to_date', frappe.datetime.month_end());
                } else if (timespan === 'Yearly') {
                    frappe.query_report.set_filter_value('from_date', frappe.datetime.year_start());
                    frappe.query_report.set_filter_value('to_date', frappe.datetime.year_end());
                }
            }
        },
        {
            "fieldname": "from_date",
            "label": __("From Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.month_start(),
            "reqd": 1
        },
        {
            "fieldname": "to_date",
            "label": __("To Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.month_end(),
            "reqd": 1
        },
        {
            "fieldname": "supplier",
            "label": __("Supplier"),
            "fieldtype": "Link",
            "options": "Supplier"
        },
        {
            "fieldname": "project",
            "label": __("Project"),
            "fieldtype": "Link",
            "options": "Project"
        }
    ]
};
