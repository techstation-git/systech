// Copyright (c) 2025, Tati and contributors
// For license information, please see license.txt

frappe.ui.form.on('Asset Revaluation', {
    asset: function (frm) {
        if (frm.doc.asset) {
            frappe.call({
                method: "systech.systech.doctype.asset_revaluation.asset_revaluation.get_asset_details",
                args: {
                    asset: frm.doc.asset,
                    revaluation_date: frm.doc.revaluation_date || frappe.datetime.get_today()
                },
                callback: function (r) {
                    if (r.message) {
                        frm.set_value('company', r.message.company);
                        frm.set_value('original_cost', r.message.original_cost);
                        frm.set_value('depreciation_method', r.message.depreciation_method);
                        frm.set_value('total_useful_life', r.message.total_useful_life);
                        frm.set_value('accumulated_depreciation', r.message.accumulated_depreciation);
                        frm.set_value('net_book_value', r.message.net_book_value);
                        frm.set_value('current_asset_value', r.message.current_asset_value);
                        frm.set_value('remaining_useful_life', r.message.remaining_useful_life);
                        frm.set_value('remaining_useful_life_months', r.message.remaining_useful_life_months);
                        frm.trigger('calculate_new_annual_depreciation');
                    }
                }
            });
        }

    },
    revaluation_date: function (frm) {
        if (frm.doc.asset) {
            frm.trigger('asset');
        }
    },
    new_asset_value: function (frm) {
        if (frm.doc.new_asset_value != undefined) {
            // Input is now the adjustment amount (additive)
            let diff = frm.doc.new_asset_value;
            frm.set_value('revaluation_difference', diff);
            frm.set_value('revaluation_type', diff >= 0 ? "Increase" : "Decrease");
            frm.trigger('calculate_new_annual_depreciation');
        }
    },
    new_remaining_life: function (frm) {
        frm.trigger('calculate_new_annual_depreciation');
    },
    new_remaining_life_months: function (frm) {
        // Redundant logic removed as visibility is now handled by depends_on
        frm.trigger('calculate_new_annual_depreciation');
    },
    life_input_mode: function (frm) {
        // Clear both values when mode changes to prevent hidden values from affecting logic
        frm.set_value('new_remaining_life', 0);
        frm.set_value('new_remaining_life_months', 0);
        frm.trigger('calculate_new_annual_depreciation');
    },
    calculate_new_annual_depreciation: function (frm) {
        let current_nbv = frm.doc.net_book_value || 0;
        let value_adjustment = frm.doc.new_asset_value || 0;
        let total_new_value = flt(current_nbv) + flt(value_adjustment);

        let remaining_months = frm.doc.remaining_useful_life_months || (flt(frm.doc.remaining_useful_life) * 12);
        let additional_months = 0;

        if (frm.doc.life_input_mode == "Months") {
            additional_months = flt(frm.doc.new_remaining_life_months);
        } else {
            additional_months = flt(frm.doc.new_remaining_life) * 12;
        }

        let total_remaining_months = remaining_months + additional_months;

        if (total_remaining_months > 0) {
            let total_remaining_years = total_remaining_months / 12;
            let new_annual_depr = total_new_value / total_remaining_years;
            frm.set_value('new_annual_depreciation', new_annual_depr);
        } else {
            frm.set_value('new_annual_depreciation', 0);
        }
    }
});
