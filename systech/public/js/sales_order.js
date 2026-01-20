frappe.ui.form.on('Sales Order', {
    refresh: function (frm) {
        if (frm.doc.workflow_state === 'Locked' || frm.doc.workflow_state === 'Release Requested') {
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


        if (frm.doc.workflow_state === 'Locked') {
            // Hide the 'Create' button which normally allows making Invoices/Delivery Notes
            // Use a timeout to ensure toolbar is rendered
            setTimeout(function () {
                frm.page.remove_inner_button('Create');
                // Also try hiding via class/attribute in case it's a standard group button
                frm.page.wrapper.find('button[data-label="Create"]').parent().hide();
            }, 100);
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

            if (frappe.user_roles.includes('Sales Manager') && frm.doc.workflow_state === 'Locked') {
                frm.add_custom_button(__('Release'), function () {
                    frappe.xcall('frappe.model.workflow.apply_workflow', {
                        doc: frm.doc,
                        action: 'Unreserve'
                    }).then(() => {
                        frappe.msgprint(__('Stock Released'));
                        frm.reload_doc();
                    });
                }).addClass('btn-primary');
            }
        }

        // Add Request Release Button only if Locked
        // And if the user is NOT the owner/manager (since they can just Release it themselves or via generic workflow)
        // Wait, the requirement is "show a button to request release of the stock..."
        // If I am viewing SOMEONE ELSE'S Locked order, I want to request release.
        if (frm.doc.workflow_state === 'Locked' && frm.doc.custom_release_status !== 'Requested' && frm.doc.owner !== frappe.session.user && !frappe.user_roles.includes('Sales Manager')) {
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
                                    // ... existing fields ...
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
                                    {
                                    fieldtype: 'HTML',
                                    fieldname: 'locked_orders_title',
                                    options: `<h5 class="mt-4">${__('Locked Sales Orders utilizing this stock:')}</h5>`
                                },
                                {
                                    fieldtype: 'HTML',
                                    fieldname: 'locked_orders_table',
                                    options: (() => {
                                        if (!r.message.blockers || r.message.blockers.length === 0) {
                                            return `<p class="text-muted">${__('No other Locked orders found.')}</p>`;
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
                                ]
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
    }
});
