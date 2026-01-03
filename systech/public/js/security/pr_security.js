
// // Purchase Receipt Security Script
// // Hides sensitive fields for Warehouse Keeper
// // ---------------------------------------------------------
// // Logic:
// // 1. Hide Main Totals (Grand Total, Taxes, etc)
// // 2. Hide Grid Columns (Rate, Amount, etc)
// // 3. Re-apply on every refresh and after save

// const apply_pr_security = (frm) => {
//     if (frappe.user.has_role("Warehouse Keeper")) {
//         // 1. Hide Main Totals/Prices
//         const main_fields = [
//             'base_discount_amount', 'base_grand_total', 'base_net_total',
//             'base_total', 'base_total_taxes_and_charges', 'discount_amount',
//             'grand_total', 'net_total', 'total', 'total_taxes_and_charges', 'taxes',
//             'buying_price_list', 'price_list_currency', 'plc_conversion_rate', 'currency', 'conversion_rate'
//         ];

//         main_fields.forEach(field => {
//             frm.set_df_property(field, 'hidden', 1);
//         });

//         // 2. Hide Child Table Columns (Items)
//         const hide_grid = () => {
//             if (!frm.fields_dict['items']) return;
//             const grid = frm.fields_dict['items'].grid;
//             const columns_to_hide = [
//                 'rate', 'amount', 'base_rate', 'base_amount', 'net_rate',
//                 'net_amount', 'valuation_rate', 'price_list_rate',
//                 'discount_amount', 'discount_percentage', 'rm_supp_cost',
//                 'landed_cost_voucher_amount'
//             ];

//             if (grid) {
//                 // Method 1: Standard
//                 columns_to_hide.forEach(field => {
//                     grid.update_docfield_property(field, 'hidden', 1);
//                     grid.update_docfield_property(field, 'print_hide', 1);
//                 });

//                 // Method 2: Brute Force on Docfields
//                 if (grid.docfields) {
//                     grid.docfields.forEach(df => {
//                         if (columns_to_hide.includes(df.fieldname)) {
//                             df.hidden = 1;
//                             df.print_hide = 1;
//                             df.read_only = 1; // Extra layer: make it read only so it's harder to mess with if seen
//                         }
//                     });
//                 }

//                 // Force Grid Refresh
//                 grid.refresh();

//                 // Method 3: Hiding in DOM (Last Resort, prevents flickering)
//                 // This is handled by grid.refresh() respecting hidden property
//             }
//         };

//         hide_grid();
//         // Retry logic: Run repeatedly to catch any re-renders (e.g. after save)
//         setTimeout(hide_grid, 500);
//         setTimeout(hide_grid, 1500);
//     }
// };

// frappe.ui.form.on('Purchase Receipt', {
//     setup: function (frm) {
//         apply_pr_security(frm);
//     },
//     refresh: function (frm) {
//         apply_pr_security(frm);
//     },
//     onload: function (frm) {
//         apply_pr_security(frm);
//     },
//     after_save: function (frm) {
//         apply_pr_security(frm);
//         setTimeout(() => apply_pr_security(frm), 1000);
//     },
//     validate: function (frm) {
//         apply_pr_security(frm);
//     }
// });
