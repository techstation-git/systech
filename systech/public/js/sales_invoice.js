frappe.ui.form.on('Sales Invoice', {
    refresh: function (frm) {
        // Add custom Email button
        if (frm.doc.docstatus === 1 && frm.doc.customer) {
            frm.add_custom_button(__('Email'), function () {
                send_invoice_email(frm, 'customer');
            }, __('Actions'));
        }
    }
});

function send_invoice_email(frm, party_type) {
    let party_name = frm.doc.customer;

    if (!party_name) {
        frappe.msgprint(__('No customer selected'));
        return;
    }

    // Fetch email
    frappe.call({
        method: 'systech.api.email.get_party_email',
        args: {
            party_type: 'Customer',
            party_name: party_name
        },
        callback: function (r) {
            if (r.message) {
                // Email found, open dialog
                new frappe.views.CommunicationComposer({
                    doc: frm.doc,
                    frm: frm,
                    subject: __('{0}: {1}', [frm.doctype, frm.docname]),
                    recipients: r.message,
                    attach_document_print: true,
                    real_name: party_name
                });
            } else {
                // No email found
                frappe.msgprint({
                    title: __('Email Not Found'),
                    indicator: 'orange',
                    message: __(
                        'The Customer <b>{0}</b> does not have an email address.<br><br>' +
                        'Please <a href="/app/customer/{1}">add email to customer record</a> first.',
                        [party_name, party_name]
                    )
                });
            }
        }
    });
}
