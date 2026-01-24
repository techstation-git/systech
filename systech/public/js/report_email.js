// Add standalone "Send to Email" button to all reports
frappe.pages['query-report'].on_page_load = function (wrapper) {
    // Wait for report to be ready
    setTimeout(function () {
        let page = wrapper.page;

        // Add standalone button (not in menu)
        page.add_inner_button(__('Send to Email'), function () {
            let report_name = frappe.get_route()[1];
            let filters = frappe.query_report.get_filter_values();

            show_email_report_dialog(report_name, filters);
        }, null, 'primary');
    }, 500);
};

function show_email_report_dialog(report_name, filters) {
    let party_type = null;
    let party_name = null;

    if (filters.customer) {
        party_type = 'Customer';
        party_name = filters.customer;
    } else if (filters.supplier) {
        party_type = 'Supplier';
        party_name = filters.supplier;
    }

    const open_dialog = (default_email = "") => {
        let d = new frappe.ui.Dialog({
            title: __('Email Report: {0}', [report_name]),
            fields: [
                {
                    fieldtype: 'Data',
                    fieldname: 'recipients',
                    label: __('To (Email)'),
                    default: default_email,
                    reqd: 1,
                    description: __('Separate multiple emails with commas')
                },
                {
                    fieldtype: 'Data',
                    fieldname: 'subject',
                    label: __('Subject'),
                    default: __('Report: {0}', [report_name])
                },
                {
                    fieldtype: 'Small Text',
                    fieldname: 'message',
                    label: __('Message'),
                    default: __('Please find the attached report.')
                },
                {
                    fieldtype: 'Section Break'
                },
                {
                    fieldtype: 'Select',
                    fieldname: 'format',
                    label: __('Format'),
                    options: 'PDF\nExcel',
                    default: 'PDF'
                }
            ],
            primary_action_label: __('Send Email'),
            primary_action: function (values) {
                frappe.call({
                    method: 'systech.api.email.send_report_email',
                    args: {
                        report_name: report_name,
                        filters: filters,
                        recipients: values.recipients,
                        subject: values.subject,
                        message: values.message,
                        format: values.format
                    },
                    freeze: true,
                    freeze_message: __('Sending email...'),
                    callback: function (r) {
                        if (!r.exc) {
                            frappe.show_alert({
                                message: __('Email sent successfully'),
                                indicator: 'green'
                            });
                            d.hide();
                        }
                    }
                });
            }
        });
        d.show();
    };

    if (party_name) {
        frappe.call({
            method: 'systech.api.email.get_party_email',
            args: {
                party_type: party_type,
                party_name: party_name
            },
            callback: function (r) {
                open_dialog(r.message || "");
            }
        });
    } else {
        open_dialog("");
    }
}
