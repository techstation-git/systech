frappe.query_reports["Project General Report"] = {
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
            "fieldname": "customer",
            "label": __("Customer"),
            "fieldtype": "Link",
            "options": "Customer"
        },
        {
            "fieldname": "project",
            "label": __("Project"),
            "fieldtype": "Link",
            "options": "Project"
        }
    ],
    "formatter": function (value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        if (column.fieldname === 'real_profit' && data) {
            if (data.real_profit > 0) {
                value = `<span style="color:green; font-weight:bold;">${value}</span>`;
            } else if (data.real_profit < 0) {
                value = `<span style="color:red; font-weight:bold;">${value}</span>`;
            }
        }
        if (column.fieldname === 'projected_profit' && data) {
            if (data.projected_profit > 0) {
                value = `<span style="color:blue; font-weight:bold;">${value}</span>`;
            } else {
                value = `<span style="color:orange; font-weight:bold;">${value}</span>`;
            }
        }
        return value;
    },
    "after_datatable_render": function (datatable) {
        $(".report-summary-item").css({
            "cursor": "pointer",
            "transition": "transform 0.1s"
        }).on("click", function () {
            frappe.set_route("query-report", "Project Detailed Report", {
                "from_date": frappe.query_report.get_filter_value("from_date"),
                "to_date": frappe.query_report.get_filter_value("to_date"),
                "project": frappe.query_report.get_filter_value("project")
            });
        }).on("mouseenter", function () {
            $(this).css("transform", "translateY(-2px)");
        }).on("mouseleave", function () {
            $(this).css("transform", "translateY(0)");
        });
    },
    "onload": function (report) {
        // Add Send to Email button
        report.page.add_inner_button(__('Send to Email'), function () {
            let d = new frappe.ui.Dialog({
                title: __('Email Report'),
                fields: [
                    { fieldtype: 'Data', fieldname: 'email', label: __('To'), reqd: 1 },
                    { fieldtype: 'Data', fieldname: 'subject', label: __('Subject'), default: 'Project General Report' },
                    { fieldtype: 'Select', fieldname: 'format', label: __('Format'), options: 'PDF\nExcel', default: 'PDF' }
                ],
                primary_action_label: __('Send'),
                primary_action: function (values) {
                    frappe.call({
                        method: 'systech.api.email.send_report_email',
                        args: {
                            report_name: 'Project General Report',
                            filters: report.get_values(),
                            recipients: values.email,
                            subject: values.subject,
                            message: 'Please find attached.',
                            format: values.format
                        },
                        freeze: true,
                        callback: function (r) {
                            if (!r.exc) {
                                frappe.show_alert({ message: __('Sent!'), indicator: 'green' });
                                d.hide();
                            }
                        }
                    });
                }
            });
            d.show();
        }, null, 'primary');
    }
};
