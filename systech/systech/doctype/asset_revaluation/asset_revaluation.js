// Copyright (c) 2025, Tati and contributors
// For license information, please see license.txt

frappe.ui.form.on('Asset Revaluation', {
    asset: function (frm) {
        if (frm.doc.asset) {
            frappe.call({
                method: "systech.systech.doctype.asset_revaluation.asset_revaluation.get_asset_details",
                args: {
                    asset: frm.doc.asset
                },
                callback: function (r) {
                    if (r.message) {
                        frm.set_value('company', r.message.company);
                        frm.set_value('original_cost', r.message.original_cost);
                        frm.set_value('depreciation_method', r.message.depreciation_method);
                        frm.set_value('total_useful_life', r.message.total_useful_life);
                        frm.set_value('accumulated_depreciation', r.message.accumulated_depreciation);
                        frm.set_value('net_book_value', r.message.net_book_value);
                        frm.set_value('remaining_useful_life', r.message.remaining_useful_life);
                    }
                }
            });
        }
        
    },
    new_asset_value: function (frm) {
        if (frm.doc.new_asset_value != undefined) {
            // Input is now the adjustment amount (additive)
            let diff = frm.doc.new_asset_value;
            frm.set_value('revaluation_difference', diff);
            frm.set_value('revaluation_type', diff >= 0 ? "Increase" : "Decrease");
        }
    },
    new_remaining_life: function (frm) {
        
    },
    new_remaining_life_months: function (frm) {
        // Redundant logic removed as visibility is now handled by depends_on
    },
    life_input_mode: function (frm) {
        // Clear both values when mode changes to prevent hidden values from affecting logic
        frm.set_value('new_remaining_life', 0);
        frm.set_value('new_remaining_life_months', 0);
    }
});
