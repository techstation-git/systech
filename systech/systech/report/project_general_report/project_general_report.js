frappe.query_reports["Project General Report"] = {
    "filters": [
        {
            "fieldname": "from_date",
            "label": __("From Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.month_start()
        },
        {
            "fieldname": "to_date",
            "label": __("To Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.month_end()
        },
        {
            "fieldname": "customer",
            "label": __("Customer"),
            "fieldtype": "Link",
            "options": "Customer",
            "on_change": function () {
                let customer = frappe.query_report.get_filter_value('customer');
                if (customer) {
                    // Filter project based on customer
                    frappe.query_report.get_filter('project').get_query = function () {
                        return { filters: { customer: customer } };
                    };
                } else {
                    frappe.query_report.get_filter('project').get_query = null;
                }
                frappe.query_report.refresh();
            }
        },
        {
            "fieldname": "project",
            "label": __("Project"),
            "fieldtype": "Link",
            "options": "Project",
            "on_change": function () {
                let project = frappe.query_report.get_filter_value('project');
                if (project && !frappe.query_report.get_filter_value('customer')) {
                    // Auto-fill customer if not selected
                    frappe.db.get_value('Project', project, 'customer', (r) => {
                        if (r && r.customer) {
                            frappe.query_report.set_filter_value('customer', r.customer);
                        }
                    });
                }
                frappe.query_report.refresh();
            }
        }
    ],
    "formatter": function (value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        if (column.fieldname === 'real_profit' && data && data.real_profit < 0) {
            value = `<span style="color:red; font-weight:bold;">${value}</span>`;
        } else if (column.fieldname === 'real_profit' && data && data.real_profit > 0) {
            value = `<span style="color:green; font-weight:bold;">${value}</span>`;
        }
        return value;
    },
    "onload": function (report) {
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
                            message: 'Please find attached the Project General Report.',
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
