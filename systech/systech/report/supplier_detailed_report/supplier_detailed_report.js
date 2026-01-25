frappe.query_reports["Supplier Detailed Report"] = {
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
            "fieldname": "supplier",
            "label": __("Supplier"),
            "fieldtype": "Link",
            "options": "Supplier",
            "on_change": function () {
                let supplier = frappe.query_report.get_filter_value('supplier');
                if (supplier) {
                    frappe.query_report.get_filter('brand').get_query = function () {
                        return {
                            query: "systech.api.report.get_brands_for_supplier",
                            filters: { supplier: supplier }
                        };
                    };
                } else {
                    frappe.query_report.get_filter('brand').get_query = null;
                }
                frappe.query_report.refresh();
            }
        },
        {
            "fieldname": "brand",
            "label": __("Brand (Item Group)"),
            "fieldtype": "Link",
            "options": "Item Group",
            "on_change": function () {
                let brand = frappe.query_report.get_filter_value('brand');
                if (brand) {
                    frappe.query_report.get_filter('supplier').get_query = function () {
                        return {
                            query: "systech.api.report.get_suppliers_for_brand",
                            filters: { brand: brand }
                        };
                    };
                } else {
                    frappe.query_report.get_filter('supplier').get_query = null;
                }
                frappe.query_report.refresh();
            }
        }
    ],
    "onload": function (report) {
        report.page.add_inner_button(__('Send to Email'), function () {
            let d = new frappe.ui.Dialog({
                title: __('Email Report'),
                fields: [
                    { fieldtype: 'Data', fieldname: 'email', label: __('To'), reqd: 1 },
                    { fieldtype: 'Data', fieldname: 'subject', label: __('Subject'), default: 'Supplier Detailed Report' },
                    { fieldtype: 'Select', fieldname: 'format', label: __('Format'), options: 'PDF\nExcel', default: 'PDF' }
                ],
                primary_action_label: __('Send'),
                primary_action: function (values) {
                    frappe.call({
                        method: 'systech.api.email.send_report_email',
                        args: {
                            report_name: 'Supplier Detailed Report',
                            filters: report.get_values(),
                            recipients: values.email,
                            subject: values.subject,
                            message: 'Please find attached the Supplier Detailed Report.',
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
