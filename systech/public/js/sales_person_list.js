frappe.listview_settings['Sales Person'] = frappe.listview_settings['Sales Person'] || {};
Object.assign(frappe.listview_settings['Sales Person'], {
    onload: function (listview) {
        // Add bulk action button
        listview.page.add_action_item(__('Set Monthly Target'), function () {
            let selected = listview.get_checked_items();

            if (selected.length === 0) {
                frappe.msgprint(__('Please select at least one Sales Person first.'));
                return;
            }

            show_target_dialog(selected);
        });
    }
});

function show_target_dialog(selected_people) {
    // Get current month and year for defaults
    let today = new Date();
    let current_year = today.getFullYear();

    let d = new frappe.ui.Dialog({
        title: __('Set Monthly Target for {0} Sales People', [selected_people.length]),
        fields: [
            {
                fieldtype: 'Link',
                fieldname: 'fiscal_year',
                label: __('Fiscal Year'),
                options: 'Fiscal Year',
                default: current_year.toString(),
                reqd: 1
            },
            {
                fieldtype: 'Link',
                fieldname: 'item_group',
                label: __('Item Group'),
                options: 'Item Group',
                default: 'All Item Groups',
                reqd: 1
            },
            {
                fieldtype: 'Column Break'
            },
            {
                fieldtype: 'Select',
                fieldname: 'target_type',
                label: __('Target Type'),
                options: 'Monthly\nYearly',
                default: 'Monthly',
                reqd: 1
            },
            {
                fieldtype: 'Float',
                fieldname: 'amount',
                label: __('Target Amount'),
                reqd: 1
            },
            {
                fieldtype: 'Section Break'
            },
            {
                fieldtype: 'HTML',
                fieldname: 'selected_list',
                options: `
                    <div class="form-section">
                        <label class="control-label">${__('Selected Sales People')}</label>
                        <div class="text-muted small">
                            ${selected_people.map(p => `• ${p.name}`).join('<br>')}
                        </div>
                    </div>
                `
            }
        ],
        primary_action_label: __('Apply Target'),
        primary_action: function (values) {
            frappe.confirm(
                __('Set target of {0} for {1} Sales People?',
                    [format_currency(values.amount), selected_people.length]
                ),
                function () {
                    frappe.call({
                        method: 'systech.api.sales_person.apply_bulk_target',
                        args: {
                            fiscal_year: values.fiscal_year,
                            item_group: values.item_group,
                            target_type: values.target_type,
                            amount: values.amount,
                            sales_people: selected_people.map(p => p.name)
                        },
                        freeze: true,
                        freeze_message: __('Applying targets...'),
                        callback: function (r) {
                            if (r.message && r.message.status === 'success') {
                                frappe.show_alert({
                                    message: __('Successfully updated {0} Sales People', [r.message.updated_count]),
                                    indicator: 'green'
                                });
                                d.hide();
                                cur_list.refresh();
                            }
                        }
                    });
                }
            );
        }
    });

    d.show();
}
