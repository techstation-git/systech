frappe.ui.form.on('Bulk Sales Person Target', {
    refresh: function (frm) {
        frm.disable_save();

        // Add Preview button
        frm.add_custom_button(__('Preview Changes'), function () {
            if (!frm.doc.fiscal_year || !frm.doc.item_group || !frm.doc.amount) {
                frappe.msgprint(__('Please fill all required fields first.'));
                return;
            }

            frappe.call({
                method: 'systech.doctype.bulk_sales_person_target.bulk_sales_person_target.preview_changes',
                args: {
                    fiscal_year: frm.doc.fiscal_year,
                    item_group: frm.doc.item_group,
                    target_type: frm.doc.target_type,
                    amount: frm.doc.amount
                },
                callback: function (r) {
                    if (r.message) {
                        show_preview_dialog(frm, r.message);
                    }
                }
            });
        }).addClass('btn-primary');
    }
});

function show_preview_dialog(frm, preview_data) {
    let dialog = new frappe.ui.Dialog({
        title: __('Preview Target Changes'),
        size: 'large',
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'preview_table'
            }
        ],
        primary_action_label: __('Apply Targets'),
        primary_action: function () {
            let selected_people = [];
            dialog.$wrapper.find('input[type="checkbox"]:checked').each(function () {
                let sp_name = $(this).data('sales-person');
                if (sp_name) {
                    selected_people.push(sp_name);
                }
            });

            if (selected_people.length === 0) {
                frappe.msgprint(__('Please select at least one Sales Person.'));
                return;
            }

            frappe.confirm(
                __('Apply targets to {0} Sales People?', [selected_people.length]),
                function () {
                    frappe.call({
                        method: 'systech.doctype.bulk_sales_person_target.bulk_sales_person_target.apply_targets',
                        args: {
                            fiscal_year: frm.doc.fiscal_year,
                            item_group: frm.doc.item_group,
                            target_type: frm.doc.target_type,
                            amount: frm.doc.amount,
                            selected_people: selected_people
                        },
                        callback: function (r) {
                            if (r.message && r.message.status === 'success') {
                                frappe.msgprint(__('Successfully updated {0} Sales People.', [r.message.updated_count]));
                                dialog.hide();
                            }
                        }
                    });
                }
            );
        }
    });

    // Build preview table HTML
    let html = `
        <div class="mb-3">
            <button class="btn btn-xs btn-default" id="select-all-btn">${__('Select All')}</button>
            <button class="btn btn-xs btn-default ml-2" id="deselect-all-btn">${__('Deselect All')}</button>
        </div>
        <table class="table table-bordered table-condensed">
            <thead>
                <tr>
                    <th width="50"><input type="checkbox" id="select-all-checkbox" checked></th>
                    <th>${__('Sales Person')}</th>
                    <th class="text-right">${__('Current Target')}</th>
                    <th class="text-right">${__('New Target')}</th>
                    <th>${__('Status')}</th>
                </tr>
            </thead>
            <tbody>
    `;

    preview_data.forEach(function (item) {
        let row_class = item.status === 'Override' ? 'warning' : '';
        html += `
            <tr class="${row_class}">
                <td><input type="checkbox" checked data-sales-person="${item.sales_person}"></td>
                <td>${item.sales_person_name}</td>
                <td class="text-right">${format_currency(item.current_target)}</td>
                <td class="text-right">${format_currency(item.new_target)}</td>
                <td><span class="indicator ${item.status === 'Override' ? 'orange' : 'blue'}">${item.status}</span></td>
            </tr>
        `;
    });

    html += '</tbody></table>';

    dialog.fields_dict.preview_table.$wrapper.html(html);

    // Bind select all checkbox
    dialog.$wrapper.find('#select-all-checkbox').on('change', function () {
        dialog.$wrapper.find('tbody input[type="checkbox"]').prop('checked', $(this).is(':checked'));
    });

    // Bind select/deselect all buttons
    dialog.$wrapper.find('#select-all-btn').on('click', function () {
        dialog.$wrapper.find('input[type="checkbox"]').prop('checked', true);
    });

    dialog.$wrapper.find('#deselect-all-btn').on('click', function () {
        dialog.$wrapper.find('tbody input[type="checkbox"]').prop('checked', false);
    });

    dialog.show();
}
