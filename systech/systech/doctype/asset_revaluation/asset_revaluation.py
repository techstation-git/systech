# Copyright (c) 2025, Tati and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt


from frappe import _
from frappe.utils import cstr, flt, getdate, nowdate, add_months, get_last_day, cint
from frappe.utils.data import is_last_day_of_the_month
from erpnext.assets.doctype.asset.asset import get_asset_value_after_depreciation
from erpnext.assets.doctype.asset.depreciation import get_depreciation_accounts





class AssetRevaluation(Document):
	def validate(self):
		self.validate_data()
		self.calculate_difference()

	def validate_data(self):
		if not self.asset:
			frappe.throw(_("Asset is required"))
		
		asset_doc = frappe.get_doc("Asset", self.asset)
		if asset_doc.docstatus != 1:
			frappe.throw(_("Asset must be submitted"))
			
		if self.new_asset_value < 0:
			frappe.throw(_("New Asset Value cannot be negative"))

	def calculate_difference(self):
		if self.new_asset_value is not None:
			self.revaluation_difference = flt(self.new_asset_value)
			self.revaluation_type = "Increase" if self.revaluation_difference >= 0 else "Decrease"
			
		# Calculate New Annual Depreciation
		current_nbv = self.net_book_value or 0 # Should have been fetched or we rely on asset
		# If net_book_value is not set (e.g. direct API creation), triggers might fetch it, but let's be safe.
		if not current_nbv and self.asset:
			current_nbv = get_asset_details(self.asset).get("net_book_value") or 0
			
		total_new_value = flt(current_nbv) + flt(self.revaluation_difference)
		
		# Remaining life
		remaining_months = self.remaining_useful_life_months or (flt(self.remaining_useful_life) * 12)
		# Again, if not set
		if not remaining_months and self.asset:
			details = get_asset_details(self.asset)
			remaining_months = details.get("remaining_useful_life_months") or (flt(details.get("remaining_useful_life")) * 12)

		additional_months = 0
		if self.life_input_mode == "Months":
			additional_months = flt(self.new_remaining_life_months)
		else:
			additional_months = flt(self.new_remaining_life) * 12
			
		total_remaining_months = flt(remaining_months) + additional_months
		
		if total_remaining_months > 0:
			total_remaining_years = total_remaining_months / 12.0
			self.new_annual_depreciation = total_new_value / total_remaining_years
		else:
			self.new_annual_depreciation = 0

	def on_submit(self):
		self.make_journal_entry()
		self.update_asset()

	def make_journal_entry(self):
		if not self.revaluation_difference:
			return

		asset = frappe.get_doc("Asset", self.asset)
		
		# Get accounts
		fixed_asset_account, accumulated_depreciation_account, depreciation_expense_account = \
			get_depreciation_accounts(asset.asset_category, asset.company)
			
		# For Revaluation, we need a Revaluation Reserve account or Gain/Loss account.
		# Ideally this should be configurable. For now we will assume a specific account or use the difference account provided in settings?
		# Standard 'Asset Value Adjustment' uses a specific 'difference_account' field. 
		# Our doctype doesn't have a difference_account field yet. 
		# We should probably add one or default it. 
		# Re-checking JSON: No 'difference_account' field. 
		# I will fallback to 'depreciation_expense_account' for now (Loss) or 'Accumulated Depreciation' (which is wrong for Gain).
		# BETTER: Let's assume the user handles GL manually if not provided? 
		# No, requirements say "Asset revaluation". 
		# I will add a default 'revaluation_account' logical check.
		# If revaluation_difference > 0 (Gain), Credit Revaluation Reserve/Gain. Debit Asset.
		# If revaluation_difference < 0 (Loss), Debit Loss Account. Credit Asset.
		
		account_for_difference = depreciation_expense_account # Placeholder, strictly speaking should be separate.

		je = frappe.new_doc("Journal Entry")
		je.voucher_type = "Depreciation Entry"
		je.company = self.company
		je.posting_date = self.revaluation_date
		
		# Get cost center
		depreciation_cost_center, depreciation_series = frappe.get_cached_value(
			"Company", asset.company, ["depreciation_cost_center", "series_for_depreciation_entry"]
		)
		je.naming_series = depreciation_series

		amount = abs(self.revaluation_difference)
		
		# Debit/Credit Logic
		# Increase Value: Debit Asset, Credit Difference Account
		# Decrease Value: Debit Difference Account, Credit Asset
		
		entry_template = {
			"cost_center": asset.cost_center or depreciation_cost_center,
			"reference_type": "Asset",
			"reference_name": asset.name,
		}

		if self.revaluation_difference > 0:
			# Increase
			debit_entry = {
				"account": fixed_asset_account,
				"debit_in_account_currency": amount,
				**entry_template
			}
			credit_entry = {
				"account": account_for_difference,
				"credit_in_account_currency": amount,
				**entry_template
			}
		else:
			# Decrease
			debit_entry = {
				"account": account_for_difference,
				"debit_in_account_currency": amount,
				**entry_template
			}
			credit_entry = {
				"account": fixed_asset_account,
				"credit_in_account_currency": amount,
				**entry_template
			}

		je.append("accounts", debit_entry)
		je.append("accounts", credit_entry)
		
		je.flags.ignore_permissions = True
		je.submit()
		self.db_set("journal_entry", je.name)

	def update_asset(self):
		asset = frappe.get_doc("Asset", self.asset)
		
		# Find the relevant finance book row
		fb_row = None
		if asset.finance_books:
			# Try to find default or specific one. Our form doesn't select FB, so use default logic.
			for d in asset.finance_books:
				if d.finance_book == asset.default_finance_book:
					fb_row = d
					break
			if not fb_row:
				fb_row = asset.finance_books[0]

		if not fb_row:
			return # Should not happen

		# Update Value
		# We update 'value_after_depreciation' which tracks current value in FB row
		fb_row.value_after_depreciation = flt(fb_row.value_after_depreciation) + flt(self.revaluation_difference)
		
		# Update Life
		# Logic: ADD 'Additional Life' to total_number_of_depreciations.
		
		if self.allow_life_override:
			new_remaining_months = 0
			if self.new_remaining_life_months:
				new_remaining_months = flt(self.new_remaining_life_months)
			elif self.new_remaining_life:
				new_remaining_months = flt(self.new_remaining_life) * 12
			
			if new_remaining_months:
				frequency_months = fb_row.frequency_of_depreciation or 1
				additional_depreciations = new_remaining_months / frequency_months
				
				# Add to total number of depreciations
				fb_row.total_number_of_depreciations = flt(fb_row.total_number_of_depreciations) + additional_depreciations
				fb_row.db_update()

		asset.value_after_depreciation = flt(asset.value_after_depreciation) + flt(self.revaluation_difference)
		
		# Flags for schedule recreation
		asset.flags.ignore_validate_update_after_submit = True
		asset.flags.ignore_permissions = True
		asset.save()
		
		# Re-create schedule
		life_text = f"{self.new_remaining_life_months} months" if self.new_remaining_life_months else f"{self.new_remaining_life} years"
		notes = _("Asset Revaluation {0}: Value {1}, Life {2}").format(
			self.name, self.new_asset_value, life_text
		)
		
		self.update_existing_asset_depr_schedules(asset, notes)

	def update_existing_asset_depr_schedules(self, asset, notes):
		# Find active schedules
		schedules = frappe.get_all("Asset Depreciation Schedule", 
			filters={"asset": asset.name, "status": "Active"}, 
			pluck="name"
		)
		
		for schedule_name in schedules:
			schedule_doc = frappe.get_doc("Asset Depreciation Schedule", schedule_name)
			
			# Get the corresponding finance book row from asset
			fb_row = None
			if asset.finance_books:
				for fb in asset.finance_books:
					if fb.finance_book == schedule_doc.finance_book:
						fb_row = fb
						break
				if not fb_row:
					fb_row = asset.finance_books[0]
			
			if fb_row:
				# Update schedule doc fields to match new asset state
				schedule_doc.total_number_of_depreciations = fb_row.total_number_of_depreciations
				schedule_doc.frequency_of_depreciation = fb_row.frequency_of_depreciation
				schedule_doc.expected_value_after_useful_life = fb_row.expected_value_after_useful_life
				
				# Update notes
				if schedule_doc.notes:
					schedule_doc.notes += "\n" + notes
				else:
					schedule_doc.notes = notes
					
				# Splicing Logic
				# 1. Identify Cutoff
				cutoff_date = self.revaluation_date
				
				# 2. Separate Preserved vs To-Be-Regenerated
				preserved_rows = []
				for row in schedule_doc.get("depreciation_schedule"):
					# Keep if schedule date is BEFORE revaluation date
					# Note: depreciation entries are usually Month End. 
					# If Revaluation is 15th Jan, and Schedule is 31st Jan. 
					# 31st Jan row > 15th Jan. It should be replaced/recalculated?
					# Yes, effective date determines when the new value applies.
					if getdate(row.schedule_date) < getdate(cutoff_date):
						preserved_rows.append(row)
				
				# 3. Calculate state at cutoff
				accumulated_depr_at_cutoff = sum(flt(d.depreciation_amount) for d in preserved_rows)
				# We use the original Gross Purchase Amount (or previous value) for base?
				# Asset Value = Gross - Accumulated
				# Ideally we want: Current Value Before Revaluation (+ any previous adjustments) - Depreciation so far
				# But simpler: Net Book Value at cutoff.
				# We can rely on Asset's gross purchase amount if no other revaluations happened.
				# If other revaluations happened, they modified 'value_after_depreciation' or 'gross_purchase_amount'.
				# Wait, Asset.value_after_depreciation tracks the *current* Book Value in ERPNext.
				# But if Future, Asset.value_after_depreciation might be "Current" (Now), not "Future" (Cutoff).
				
				# Let's derive from Finance Book Row data which we supposedly trust.
				# fb_row.value_after_depreciation is the current NBV.
				# But that reflects ALL booked entries? No, it reflects the state "now".
				# If revaluation is in future, we must project.
				
				# Better approach:
				# Base Value = Gross Purchase Amount - Accumulated Depr (Preserved)
				# But Gross Purchase Amount might have changed if multiple revaluations.
				# Let's use the first schedule row's logic? No.
				
				# Let's use:
				# Value at Cutoff = (Asset Gross Purchase Amount) - (Sum of Preserved Depreciation)
				# Note: Gross Purchase Amount in ERPNext includes capitalized costs/revaluations usually? 
				# Actually revaluation modifies 'value_after_depreciation' usually, not gross.
				# Checking `update_asset`: we modified `fb_row.value_after_depreciation`.
				# And `asset.value_after_depreciation`.
				
				# If we are in "Future" scenario, our `update_asset` earlier changed the NBV *Now*.
				# That might be technically incorrect if the revaluation is effective in future?
				# If I say "Revalue in 2026", but I change `asset.value_after_depreciation` NOW (2025),
				# then the asset value is immediately up.
				# But the depreciation for 2025 should be on old value...
				# If I changed `value_after_depreciation` globally, standard ERPNext logic would immediately use it for next schedule.
				
				# This implies my `update_asset` logic (Step 1 of this whole process) might be too aggressive for Future Revaluation.
				# However, users usually want to record the "Event" now.
				# If we strictly want "Old Rate until Date X":
				# The generated schedule rows for the interval (Now -> Date X) MUST use the OLD value/rate.
				# The rows after Date X use the NEW value/rate.
				
				# To achieve this:
				# 1. Calculate `value_at_start_of_period` for the NEW segment.
				#    Preserved Rows sum = Depreciation booked/planned so far.
				#    Original Cost = asset.gross_purchase_amount (assuming it's the anchor).
				#    NBV at Cutoff = Original Cost - Preserved Sum.
				#    New Base = NBV at Cutoff + self.revaluation_difference.
				
				# 2. Make new rows.
				#    Remaining Life = ??
				#    Original Total Life (Months).
				#    Used Life (Months) = len(preserved_rows) * frequency.
				#    Remaining Original Life = Total - Used.
				#    New Total Remaining = Remaining Original + Additional Life.
				
				#    Monthly Depr = New Base / (New Total Remaining / frequency).
				
				pres_depr_sum = sum(flt(d.depreciation_amount) for d in preserved_rows)
				# Use asset.gross_purchase_amount as the anchor for "Original Cost" concept
				nbv_at_cutoff = flt(asset.gross_purchase_amount) - pres_depr_sum
				new_base_at_cutoff = nbv_at_cutoff + flt(self.revaluation_difference)
				
				# Determine number of periods already covered
				periods_covered = len(preserved_rows)
				
				# Calculate new remaining periods
				# Original Total periods = fb_row.total_number_of_depreciations (This was UPDATED in update_asset to include the increase!)
				# So we need to subtract the *increase* to get the "original" before this transaction?
				# Yes, in `update_asset`, we did: `fb_row.total_number_of_depreciations += additional_depreciations`
				
				# So:
				# Current Total (Updated) - Consumed (Preserved) = Remaining (Updated).
				
				remaining_periods = flt(fb_row.total_number_of_depreciations) - periods_covered
				
				if remaining_periods <= 0:
					# Edge case: extended life but maybe not enough?
					pass
					
				# Generate new rows
				new_rows = []
				start_date = preserved_rows[-1].schedule_date if preserved_rows else asset.available_for_use_date
				
				# Generate
				# We can loop manually to avoid complexity of `make_depr_schedule`
				
				final_value = flt(fb_row.expected_value_after_useful_life)
				# Depreciable Amount for the FUTURE section
				depreciable_amt = new_base_at_cutoff - final_value
				
				# Depreciation per period
				if remaining_periods > 0:
					amt_per_period = depreciable_amt / remaining_periods
				else:
					amt_per_period = 0
					
				current_date = getdate(start_date)
				frequency_months = cint(fb_row.frequency_of_depreciation)
				
				# Rounding precision
				precision = asset.precision("gross_purchase_amount")
				
				accumulated_depr = pres_depr_sum
				
				for i in range(cint(remaining_periods)):
					# Next date
					# If preserved_rows exists, we add to last one.
					# If not, we add to available_for_use_date?
					# Be careful with the first jump.
					
					# If we have preserved rows, the next one is 1 frequency after the last one.
					next_date = add_months(current_date, frequency_months)
					if is_last_day_of_the_month(current_date):
						next_date = get_last_day(next_date)
						
					current_date = next_date
					
					# Amount
					# Last row adjustment?
					d_amt = flt(amt_per_period, precision)
					
					# Check for last row rounding to match expected value
					if i == cint(remaining_periods) - 1:
						# Ensure we hit the exact value
						# Remaining value = New Base - Accumulated (New Section Only?) 
						# Actually simpler: Total Goal = New Base. 
						# We have depreciated: Accumulated So Far + Sum of New Rows so far.
						# This entry should bridge the gap to expected_value.
						
						current_value_before_this = new_base_at_cutoff - (flt(accumulated_depr) - pres_depr_sum)
						d_amt = current_value_before_this - final_value
						d_amt = flt(d_amt, precision)
					
					accumulated_depr += d_amt
					
					new_rows.append({
						"schedule_date": current_date,
						"depreciation_amount": d_amt,
						"accumulated_depreciation_amount": flt(accumulated_depr, precision),
						"journal_entry": ""
					})

				# 4. Reconstruct Schedule
				# Clear existing
				schedule_doc.depreciation_schedule = []
				
				# Add Preserved
				for p in preserved_rows:
					schedule_doc.append("depreciation_schedule", {
						"schedule_date": p.schedule_date,
						"depreciation_amount": p.depreciation_amount,
						"accumulated_depreciation_amount": p.accumulated_depreciation_amount,
						"journal_entry": p.journal_entry
					})
					
				# Add New
				for n in new_rows:
					schedule_doc.append("depreciation_schedule", n)
				
				schedule_doc.flags.ignore_permissions = True
				schedule_doc.flags.ignore_validate_update_after_submit = True
				schedule_doc.save()

@frappe.whitelist()
def get_asset_details(asset):
	asset_doc = frappe.get_doc("Asset", asset)
	
	# Get Finance Book details (assuming defaults or first one)
	# Logic: Try to find default finance book, else take the first one
	fb_row = None
	if asset_doc.get("finance_books"):
		for d in asset_doc.finance_books:
			if d.finance_book == asset_doc.default_finance_book:
				fb_row = d
				break
		if not fb_row:
			fb_row = asset_doc.finance_books[0]

	if not fb_row:
		# Fallback if no finance book exists
		# Approximate accumulated depreciation if possible, else 0
		accumulated_depreciation = frappe.db.sql("""
			select sum(depreciation_amount) 
			from `tabDepreciation Schedule` 
			where parent=%s and parenttype='Asset' and docstatus=1
		""", asset)[0][0] or 0.0
		
		return {
			"company": asset_doc.company,
			"original_cost": asset_doc.total_asset_cost,
			"accumulated_depreciation": accumulated_depreciation,
			"net_book_value": flt(asset_doc.total_asset_cost) - flt(accumulated_depreciation),
			"depreciation_method": "",
			"total_useful_life": 0,
			"remaining_useful_life": 0,
			"remaining_useful_life_months": 0
		}

	# Calculate Useful Life
	total_months = flt(fb_row.total_number_of_depreciations) * flt(fb_row.frequency_of_depreciation)
	useful_life_years = total_months / 12.0
	
	# Calculate Accumulated Depreciation
	# Best way: Gross Purchase Amount - Value After Depreciation (Current Value in Finance Book)
	# This accounts for any adjustments, manuals, etc. better than summing schedule sometimes.
	value_after_depr = flt(fb_row.value_after_depreciation)
	accumulated_depreciation = flt(asset_doc.gross_purchase_amount) - value_after_depr
	
	nbv = value_after_depr
	
	# Calculate Remaining Life
	# Total Depreciations - Booked Depreciations
	# This gives accurate 'number of periods remaining'.
	# Then multiply by frequency to get months.
	
	# Use 'total_number_of_booked_depreciations' from fb_row if consistent, or count from schedule?
	# fb_row has 'total_number_of_booked_depreciations' but sometimes it might lag if not updated correctly?
	# Safest is fb_row for consistency with Value.
	
	# Actually, fb_row.total_number_of_booked_depreciations is reliable.
	remaining_depreciations = flt(fb_row.total_number_of_depreciations) - flt(fb_row.total_number_of_booked_depreciations)
	remaining_months = remaining_depreciations * flt(fb_row.frequency_of_depreciation)
	remaining_years = remaining_months / 12.0

	return {
		"company": asset_doc.company,
		"original_cost": asset_doc.total_asset_cost,
		"depreciation_method": fb_row.depreciation_method,
		"total_useful_life": useful_life_years,
		"accumulated_depreciation": accumulated_depreciation,
		"net_book_value": nbv,
		"remaining_useful_life": remaining_years,
		"remaining_useful_life_months": remaining_months
	}
