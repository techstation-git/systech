frappe.ui.form.on('Purchase Order', {
    refresh: function (frm) {
        // Add custom Email button
        if (frm.doc.docstatus === 1 && frm.doc.supplier) {
            frm.add_custom_button(__('Email'), function () {
                send_purchase_email(frm, 'supplier');
            }, __('Actions'));
        }
    }
});

function send_purchase_email(frm, party_type) {
    let party_name = frm.doc.supplier;

    if (!party_name) {
        frappe.msgprint(__('No supplier selected'));
        return;
    }

    // Fetch email
    frappe.call({
        method: 'systech.api.email.get_party_email',
        args: {
            party_type: 'Supplier',
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
                        'The Supplier <b>{0}</b> does not have an email address.<br><br>' +
                        'Please <a href="/app/supplier/{1}">add email to supplier record</a> first.',
                        [party_name, party_name]
                    )
                });
            }
        }
    });
}
