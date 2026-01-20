// Auto-populate customer email in email dialogs for sales documents
frappe.ui.form.on('Sales Order', {
    onload: function (frm) {
        setup_email_auto_populate(frm);
    }
});

frappe.ui.form.on('Sales Invoice', {
    onload: function (frm) {
        setup_email_auto_populate(frm);
    }
});

frappe.ui.form.on('Quotation', {
    onload: function (frm) {
        setup_email_auto_populate(frm);
    }
});

function setup_email_auto_populate(frm) {
    // Override the standard email dialog
    frm.email_doc = function () {
        // Get customer email
        let customer_email = frm.doc.contact_email || frm.doc.email_id;

        if (!customer_email && frm.doc.customer) {
            // Try to fetch from customer record
            frappe.call({
                method: 'systech.api.email.get_customer_email',
                args: {
                    customer: frm.doc.customer
                },
                callback: function (r) {
                    if (r.message) {
                        open_email_dialog(frm, r.message);
                    } else {
                        show_missing_email_warning(frm);
                    }
                }
            });
        } else if (customer_email) {
            open_email_dialog(frm, customer_email);
        } else {
            show_missing_email_warning(frm);
        }
    };
}

function open_email_dialog(frm, email) {
    new frappe.views.CommunicationComposer({
        doc: frm.doc,
        frm: frm,
        subject: __('{0}: {1}', [frm.doctype, frm.docname]),
        recipients: email,
        attach_document_print: true,
        real_name: frm.doc.customer
    });
}

function show_missing_email_warning(frm) {
    frappe.msgprint({
        title: __('Customer Email Missing'),
        indicator: 'orange',
        message: __(
            'The customer <b>{0}</b> does not have an email address.<br><br>' +
            'Please either:<br>' +
            '1. <a href="/app/customer/{1}">Add email to customer record</a><br>' +
            '2. Enter email manually in the dialog',
            [frm.doc.customer_name || frm.doc.customer, frm.doc.customer]
        )
    });

    // Open dialog anyway but without pre-filled email
    new frappe.views.CommunicationComposer({
        doc: frm.doc,
        frm: frm,
        subject: __('{0}: {1}', [frm.doctype, frm.docname]),
        attach_document_print: true,
        real_name: frm.doc.customer
    });
}
