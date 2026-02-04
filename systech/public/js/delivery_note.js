frappe.ui.form.on('Delivery Note', {
    refresh: function (frm) {
        if (frm.doc.docstatus === 0 && !frm.doc.__islocal) {
            // Check stock status on load for existing drafts
            frm.trigger('check_stock_availability');
        }
    },

    validate: function (frm) {
        if (frm.doc.docstatus === 0) {
            frm.trigger('check_stock_availability');
        }
    },

    check_stock_availability: function (frm) {
        frappe.call({
            method: "systech.services.workflow.validate_dn_stock",
            args: {
                docname: frm.doc.name
            },
            callback: function (r) {
                if (r.message && r.message.status === "failed") {
                    // Show warning / blocked status
                    handle_insufficient_stock(frm, r.message);
                } else {
                    // Clear any previous indicators if possible
                    frm.dashboard.clear_headline();
                }
            }
        });
    }
});

function handle_insufficient_stock(frm, data) {
    let msg = __("Insufficient Actual Stock. Some items are reserved by other Approved Orders.");

    // Show headline
    frm.dashboard.set_headline_alert(
        `<div class="row">
            <div class="col-xs-12">
                <span class="indicator red">${msg}</span>
            </div>
        </div>`
    );

    // Show Dialog with conflict details
    let items_html = data.items.map(i => `<li><b>${i.item_code}</b>: Req ${i.required}, Available ${i.available}</li>`).join("");

    let conflict_html = "";
    if (data.blockers && data.blockers.length > 0) {
        conflict_html = "<b>Conflicting Orders:</b><br><ul>";
        data.blockers.forEach(b => {
            conflict_html += `<li><a href="/app/sales-order/${b.name}">${b.name}</a> (${b.customer}) - Qty: ${b.qty}</li>`;
        });
        conflict_html += "</ul>";
    }

    frappe.msgprint({
        title: __('Stock Unavailable'),
        message: `<ul>${items_html}</ul><hr>${conflict_html}`,
        indicator: 'red'
    });

    // Add Request Release Button
    frm.add_custom_button(__('Request Stock Release'), function () {
        request_release_from_blockers(frm, data.blockers);
    }).addClass('btn-danger');
}

function request_release_from_blockers(frm, blockers) {
    if (!blockers || blockers.length === 0) {
        frappe.msgprint("No specific conflicting orders found to release from.");
        return;
    }

    let d = new frappe.ui.Dialog({
        title: 'Request Stock Release',
        fields: [
            {
                label: 'Select Order to Release From',
                fieldname: 'source_order',
                fieldtype: 'Select',
                options: blockers.map(b => b.name),
                reqd: 1
            }
        ],
        primary_action_label: 'Send Request',
        primary_action: function (values) {
            frappe.call({
                method: "systech.services.workflow.request_release",
                args: {
                    docname: values.source_order, // The APPROVED order holding stock
                    source_docname: frm.doc.name // THIS Delivery Note asking for it
                },
                callback: function (r) {
                    d.hide();
                    frappe.msgprint("Release Request Sent to Managers");
                }
            });
        }
    });

    d.show();
}
