frappe.ui.form.on('Sales Order', {
    refresh: function (frm) {
        if (frm.doc.workflow_state === 'Approved' || frm.doc.workflow_state === 'Release Requested') {
            // Check if current user is owner or manager
            let is_manager = frappe.user_roles.includes('Sales Manager') || frappe.user_roles.includes('System Manager');
            let is_owner = frm.doc.owner === frappe.session.user;

            if (!is_manager && !is_owner) {
                console.log('Hiding prices for user:', frappe.session.user);
                // Hide prices
                ['amount_eligible_for_commission', 'total_commission', 'base_total_commission', 'total_qty', 'total_net_weight', 'total', 'net_total', 'base_total', 'base_net_total', 'taxes_and_charges_added', 'taxes_and_charges_deducted', 'base_taxes_and_charges_added', 'base_taxes_and_charges_deducted', 'grand_total', 'base_grand_total', 'rounded_total', 'base_rounded_total', 'in_words', 'base_in_words', 'total_advance', 'outstanding_amount', 'disable_rounded_total', 'apply_discount_on', 'base_discount_amount', 'additional_discount_percentage', 'discount_amount', 'other_charges_calculation', 'to_date', 'coupon_code'].forEach(field => {
                    frm.set_df_property(field, 'hidden', 1);
                });

                // Hide prices in child table 'items'
                const hide_child_fields = () => {
                    // Item Grid
                    ['rate', 'amount', 'net_rate', 'net_amount', 'discount_amount', 'base_rate', 'base_amount', 'price_list_rate', 'base_price_list_rate'].forEach(field => {
                        frm.fields_dict.items.grid.update_docfield_property(field, 'hidden', 1);
                        // CSS Fallback
                        frm.fields_dict.items.$wrapper.find(`.grid-static-col[data-fieldname="${field}"]`).hide();
                    });

                    // Sales Team (Commission) Grid
                    if (frm.fields_dict.sales_team) {
                        ['incentives', 'allocated_amount', 'allocated_percentage'].forEach(field => {
                            frm.fields_dict.sales_team.grid.update_docfield_property(field, 'hidden', 1);
                            frm.fields_dict.sales_team.$wrapper.find(`.grid-static-col[data-fieldname="${field}"]`).hide();
                        });
                        frm.fields_dict.sales_team.grid.refresh();
                    }

                    // Payment Schedule Grid
                    if (frm.fields_dict.payment_schedule) {
                        ['payment_amount', 'outstanding', 'paid_amount', 'discounted_amount', 'base_payment_amount'].forEach(field => {
                            frm.fields_dict.payment_schedule.grid.update_docfield_property(field, 'hidden', 1);
                            frm.fields_dict.payment_schedule.$wrapper.find(`.grid-static-col[data-fieldname="${field}"]`).hide();
                        });
                        frm.fields_dict.payment_schedule.grid.refresh();
                    }

                    // Taxes Grid
                    if (frm.fields_dict.taxes) {
                        ['tax_amount', 'total', 'base_tax_amount', 'base_total'].forEach(field => {
                            frm.fields_dict.taxes.grid.update_docfield_property(field, 'hidden', 1);
                            frm.fields_dict.taxes.$wrapper.find(`.grid-static-col[data-fieldname="${field}"]`).hide();
                        });
                        frm.fields_dict.taxes.grid.refresh();
                    }

                    frm.fields_dict.items.grid.refresh();
                };

                // Execute immediately and after a short delay to ensure grid is ready
                hide_child_fields();
                setTimeout(hide_child_fields, 500);
            }
        }


        if (frm.doc.workflow_state === 'Approved' && frm.doc.status !== 'Closed') {
            // Hide standard buttons by removing them item by item
            // Using polling to capture late-loading buttons
            const hideButtons = () => {
                // Double check state to prevent race conditions during navigation
                if (frm.doc.workflow_state !== 'Approved') return;

                const to_hide = [
                    // Create Menu Items
                    ['Pick List', 'Create'],
                    ['Delivery Note', 'Create'],
                    ['Work Order', 'Create'],
                    ['Sales Invoice', 'Create'],
                    ['Material Request', 'Create'],
                    ['Purchase Order', 'Create'],
                    ['Request for Raw Materials', 'Create'],
                    ['Project', 'Create'],
                    ['Payment Request', 'Create'],
                    ['Payment', 'Create'],
                    ['Subscription', 'Create'],
                    ['Maintenance Visit', 'Create'],
                    ['Maintenance Schedule', 'Create'],

                    // Status Menu Items
                    ['Hold', 'Status'],
                    ['Close', 'Status'],

                    // Solo Buttons
                    ['Update Items', null]
                ];

                to_hide.forEach(b => {
                    if (frm.remove_custom_button) {
                        try {
                            frm.remove_custom_button(b[0], b[1]);
                        } catch (e) { }
                    }
                });

                // Fallback: Try to hide the groups themselves using standard API
                try {
                    if (frm.page.remove_inner_button) {
                        frm.page.remove_inner_button('Create');
                        frm.page.remove_inner_button('Status');
                    }
                } catch (e) { }
            };

            // Run immediately
            hideButtons();

            // Poll every 200ms for 2 seconds
            let counter = 0;
            let interval = setInterval(function () {
                hideButtons();
                counter++;
                if (counter > 10) clearInterval(interval);
            }, 200);
        }


        // Add custom Email button
        if (frm.doc.docstatus === 1 && frm.doc.customer) {
            frm.add_custom_button(__('Email'), function () {
                send_document_email(frm, 'customer');
            }, __('Actions'));
        }

        // Release Request Indicator & Manager Action
        if (frm.doc.custom_release_status === 'Requested') {
            frm.dashboard.set_headline_alert(
                `<div class="row">
                    <div class="col-xs-12">
                        <span class="indicator orange">${__('Stock Release Requested')}</span>
                    </div>
                </div>`
            );

            if (frappe.user_roles.includes('Sales Manager') && frm.doc.workflow_state === 'Approved') {
                frm.add_custom_button(__('Release Stock'), function () {
                    // Dialog for partial release
                    let fields = frm.doc.items.map((item, idx) => {
                        return [
                            {
                                fieldtype: 'Read Only',
                                fieldname: `item_info_${idx}`,
                                label: `Item ${idx + 1}: ${item.item_code}`,
                                default: `${item.item_name} (Current: ${item.qty})`
                            },
                            {
                                fieldtype: 'Float',
                                fieldname: `release_qty_${idx}`,
                                label: __('Qty to Release'),
                                default: 0,
                                reqd: 1
                            },
                            {
                                fieldtype: 'Column Break'
                            }
                        ];
                    }).flat();

                    let d = new frappe.ui.Dialog({
                        title: __('Release Stock Quantities'),
                        fields: fields,
                        primary_action_label: __('Release'),
                        primary_action: function (values) {
                            d.hide();

                            let item_releases = {};
                            frm.doc.items.forEach((item, idx) => {
                                item_releases[item.name] = values[`release_qty_${idx}`];
                            });

                            frappe.call({
                                method: 'systech.services.workflow.release_stock_manually',
                                args: {
                                    docname: frm.doc.name,
                                    item_releases: item_releases
                                },
                                freeze: true,
                                callback: function (r) {
                                    if (!r.exc) {
                                        frappe.show_alert({
                                            message: r.message.closed ? __('Stock released and Order Closed') : __('Stock released and quantities updated'),
                                            indicator: 'green'
                                        });
                                        frm.reload_doc();
                                    }
                                }
                            });
                        }
                    });
                    d.show();
                }).addClass('btn-primary');
            }
        }

        // Add Request Release Button only if Approved
        // And if the user is NOT the owner/manager (since they can just Release it themselves or via generic workflow)
        // Wait, the requirement is "show a button to request release of the stock..."
        // If I am viewing SOMEONE ELSE'S Approved order, I want to request release.
        if (frm.doc.workflow_state === 'Approved' && frm.doc.custom_release_status !== 'Requested' && frm.doc.owner !== frappe.session.user && !frappe.user_roles.includes('Sales Manager')) {
            frm.add_custom_button(__('Request Release'), function () {
                frappe.confirm('Are you sure you want to request release of stock from this order?', function () {
                    frappe.call({
                        method: 'systech.services.workflow.request_release',
                        args: {
                            docname: frm.doc.name
                        },
                        callback: function (r) {
                            if (!r.exc) {
                                frappe.msgprint('Release request sent to Sales Manager.');
                                frm.reload_doc();
                            }
                        }
                    });
                });
            }).addClass('btn-primary');
        }
    },

    before_workflow_action: function (frm) {
        if (frm.selected_workflow_action === 'Submit To Manager') {
            // Before submitting to manager, copy qty to original_qty if not already set
            frm.doc.items.forEach(item => {
                if (!item.original_qty) {
                    frappe.model.set_value(item.doctype, item.name, 'original_qty', item.qty);
                }
            });

            let promise = new Promise((resolve, reject) => {
                frappe.call({
                    method: 'systech.services.workflow.check_stock_availability',
                    args: {
                        docname: frm.doc.name
                    },
                    callback: function (r) {
                        if (r.message && r.message.status === 'failed') {
                            frappe.validated = false;
                            frappe.dom.unfreeze();

                            // Construct Dialog
                            let d = new frappe.ui.Dialog({
                                title: __('Insufficient Stock'),
                                size: 'large',
                                fields: [
                                    {
                                        fieldtype: 'HTML',
                                        fieldname: 'stock_info',
                                        options: `
                                            <div class="alert alert-danger">
                                                ${__('The following items have insufficient stock:')}
                                                <ul>
                                                    ${r.message.items.map(i =>
                                            `<li><b>${i.item_code}</b>: Required ${i.required}, Available ${i.available} (Shortage: ${i.shortage})</li>`
                                        ).join('')}
                                                </ul>
                                            </div>
                                        `
                                    },
                                    {
                                        fieldtype: 'HTML',
                                        fieldname: 'locked_orders_title',
                                        options: `<h5 class="mt-4">${__('Approved Sales Orders utilizing this stock:')}</h5>`
                                    },
                                    {
                                        fieldtype: 'HTML',
                                        fieldname: 'locked_orders_table',
                                        options: (() => {
                                            if (!r.message.blockers || r.message.blockers.length === 0) {
                                                return `<p class="text-muted">${__('No other Approved orders found.')}</p>`;
                                            }
                                            return `
                                                <table class="table table-bordered table-condensed">
                                                    <thead>
                                                        <tr>
                                                            <th>${__('Order')}</th>
                                                            <th>${__('Customer')}</th>
                                                            <th>${__('Sales Person')}</th>
                                                            <th>${__('Qty Locked')}</th>
                                                            <th>${__('Items')}</th>
                                                            <th>${__('Action')}</th>
                                                        </tr>
                                                    </thead>
                                                    <tbody>
                                                        ${r.message.blockers.map(b => `
                                                            <tr>
                                                                <td>${b.name}</td>
                                                                <td>${b.customer}</td>
                                                                <td>${b.owner}</td>
                                                                <td>${b.qty}</td>
                                                                <td>${b.items.join(', ')}</td>
                                                                <td>
                                                                    <button class="btn btn-xs btn-primary btn-request-release" data-order="${b.name}" ${b.custom_release_status === 'Requested' ? 'disabled' : ''}>
                                                                        ${b.custom_release_status === 'Requested' ? __('Requested') : __('Request Release')}
                                                                    </button>
                                                                </td>
                                                            </tr>
                                                        `).join('')}
                                                    </tbody>
                                                </table>
                                            `;
                                        })()
                                    }
                                ],
                                primary_action_label: __('Close'),
                                primary_action: function () {
                                    d.hide();
                                },
                                secondary_action_label: __('Refresh'),
                                secondary_action: function () {
                                    d.hide();
                                    // Trigger the action again to re-check
                                    frm.page.actions_btn_group.find(`li a:contains("${frm.selected_workflow_action}")`).click();
                                }
                            });

                            d.show();

                            // Bind Click Event for Request Release
                            d.$wrapper.find('.btn-request-release').on('click', function () {
                                let btn = $(this);
                                let order_name = btn.data('order');
                                btn.prop('disabled', true).text(__('Requesting...'));

                                frappe.call({
                                    method: 'systech.services.workflow.request_release',
                                    args: {
                                        docname: order_name,
                                        source_docname: frm.doc.name
                                    },
                                    callback: function (res) {
                                        if (!res.exc) {
                                            frappe.show_alert({ message: __('Release requested for {0}', [order_name]), indicator: 'green' });
                                            btn.text(__('Requested')).removeClass('btn-primary').addClass('btn-success');
                                        } else {
                                            btn.prop('disabled', false).text(__('Retry'));
                                        }
                                    }
                                });
                            });

                            reject(); // Block the workflow action
                        } else {
                            resolve(); // Proceed
                        }
                    }
                });
            });
            return promise;
        }

        if (frm.selected_workflow_action === 'Approve') {
            let promise = new Promise((resolve, reject) => {
                // Safeguard: Brief delay to let UI stabilize and avoid race conditions
                setTimeout(() => {
                    // Force cleanup of any stray backdrops that might be causing "blur"
                    $('.modal-backdrop').fadeOut(100, function () { $(this).remove(); });

                    let fields = [];
                    frm.doc.items.forEach((item, idx) => {
                        fields.push({
                            fieldtype: 'Read Only',
                            fieldname: `item_info_${idx}`,
                            label: `Item ${idx + 1}: ${item.item_code}`,
                            default: `${item.item_name} (Requested: ${item.qty})`
                        });
                        fields.push({
                            fieldtype: 'Float',
                            fieldname: `approve_qty_${idx}`,
                            label: __('Qty to Approve'),
                            default: item.qty,
                            reqd: 1
                        });
                    });

                    let d = new frappe.ui.Dialog({
                        title: __('Approve Quantities'),
                        fields: fields,
                        primary_action_label: __('Approve'),
                        primary_action: function (values) {
                            // Update Doc values
                            frm.doc.items.forEach((item, idx) => {
                                let approved_qty = values[`approve_qty_${idx}`];
                                item.approved_qty = approved_qty;
                                item.qty = approved_qty;
                            });

                            d.hide();
                            // Small delay before resolving to ensure modal hiding logic completes
                            setTimeout(resolve, 300);
                        },
                        secondary_action_label: __('Cancel'),
                        secondary_action: function () {
                            d.hide();
                            reject();
                        }
                    });
                    d.show();
                }, 100);
            });
            return promise;
        }
    }
});

// Generic email sender for documents
function send_document_email(frm, party_type) {
    let party_field = party_type; // 'customer' or 'supplier'
    let party_name = frm.doc[party_field];

    if (!party_name) {
        frappe.msgprint(__('No {0} selected', [party_type]));
        return;
    }

    // Fetch email
    frappe.call({
        method: 'systech.api.email.get_party_email',
        args: {
            party_type: party_type === 'customer' ? 'Customer' : 'Supplier',
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
                // No email found, show warning
                frappe.msgprint({
                    title: __('Email Not Found'),
                    indicator: 'orange',
                    message: __(
                        'The {0} <b>{1}</b> does not have an email address.<br><br>' +
                        'Please <a href="/app/{2}/{3}">add email to {0} record</a> first.',
                        [party_type, party_name, party_type, party_name]
                    )
                });
            }
        }
    });
}
