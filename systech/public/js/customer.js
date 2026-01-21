frappe.ui.form.on('Customer', {
    refresh: function (frm) {
        // Make sales_team read-only for Sales Users (but allow Sales Managers to edit)
        if (!frappe.user.has_role('Sales Manager')) {
            frm.set_df_property('sales_team', 'read_only', 1);

            // Also disable grid buttons
            if (frm.fields_dict.sales_team && frm.fields_dict.sales_team.grid) {
                frm.fields_dict.sales_team.grid.cannot_add_rows = true;
                frm.fields_dict.sales_team.grid.grid_buttons.hide();
            }
        }
    }
});
