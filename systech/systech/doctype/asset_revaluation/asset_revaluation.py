# Copyright (c) 2025, Tati and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt


from frappe import _
from frappe.utils import cstr, flt, getdate, nowdate, add_months, get_last_day, cint, date_diff, add_days
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
		
		account_for_difference = self.revaluation_account

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
				cutoff_date = self.effective_from_date or self.revaluation_date
				
				# 2. Separate Preserved vs To-Be-Regenerated
				preserved_rows = []
				# Check for straddle
				# We iterate and find the first row that intersects or is after cutoff
				
				# Helper to get start date of a row
				def get_row_start_date(rows, idx, asset_start_date):
					if idx == 0:
						return asset_start_date
					return add_days(rows[idx-1].schedule_date, 1)

				original_rows = schedule_doc.get("depreciation_schedule")
				straddle_row_idx = -1
				
				for i, row in enumerate(original_rows):
					if getdate(row.schedule_date) < getdate(cutoff_date):
						preserved_rows.append(row)
					else:
						# This row ends after or on cutoff.
						# Check start date
						row_start = get_row_start_date(original_rows, i, asset.available_for_use_date)
						if getdate(row_start) < getdate(cutoff_date):
							# Straddle detected
							straddle_row_idx = i
						break

				# Handle Straddle
				first_target_date = None
				
				if straddle_row_idx != -1:
					row = original_rows[straddle_row_idx]
					row_start = getdate(get_row_start_date(original_rows, straddle_row_idx, asset.available_for_use_date))
					row_end = getdate(row.schedule_date)
					cutoff = getdate(cutoff_date)
					
					# Create Old Part (Start -> Cutoff - 1)
					old_part_end = add_days(cutoff, -1)
					
					# Calculate days
					total_days = date_diff(row_end, row_start) + 1
					old_days = date_diff(old_part_end, row_start) + 1
					
					if old_days > 0 and total_days > 0:
						fraction = flt(old_days) / flt(total_days)
						old_amount = flt(row.depreciation_amount) * fraction
						
						# Create a transient row object (dict)
						preserved_rows.append(frappe._dict({
							"schedule_date": old_part_end,
							"depreciation_amount": old_amount,
							"accumulated_depreciation_amount": 0.0, # Will be recalculated
							"journal_entry": row.journal_entry if row.journal_entry else "" # Keep JE if exists? Unlikely for straddle partial.
						}))
					
					# The New Part will be the first row of generation
					# Target date should be the original row end
					first_target_date = row.schedule_date

				# Re-calculate accumulated for preserved rows to ensure consistency
				running_accum = 0.0
				for p in preserved_rows:
					running_accum += flt(p.depreciation_amount)
					p.accumulated_depreciation_amount = running_accum
				
				pres_depr_sum = running_accum
				
				# CORRECT CALCULATION OF BASE VALUE AT CUTOFF
				# We know fb_row.value_after_depreciation HAS BEEN UPDATED to include the NEW ADJUSTMENT.
				# It represents the Asset Value "Now" (technically after the last booked depreciation + adjustment).
				# However, we are splicing. Some preserved_rows might be UNBOOKED (Future relative to last booking, but Past relative to Cutoff).
				# We need the value at the exact moment of Cutoff.
				# Value @ Cutoff = (Value After Last Booked + Adjustment) - (Unbooked Preserved Depreciation).
				
				# Identify unbooked preserved depreciation
				unbooked_pres_depr = 0
				for d in preserved_rows:
					if not d.journal_entry:
						unbooked_pres_depr += flt(d.depreciation_amount)
						
				# fb_row.value_after_depreciation tracks (Book Value + Adjustment).
				# But wait, fb_row.value_after_depreciation is usually updated by depreciation entries.
				# If we have unbooked entries, the FB value hasn't been reduced by them yet.
				# So fb_row.value_after_depreciation = (Last Booked Value) + (Adjustment).
				# So Value @ Cutoff = fb_row.value_after_depreciation - unbooked_pres_depr.
				
				current_val_with_adjustment = flt(fb_row.value_after_depreciation)
				new_base_at_cutoff = current_val_with_adjustment - unbooked_pres_depr
				
				# Determine number of periods already covered
				periods_covered = len(preserved_rows)
				
				# Calculate new remaining periods
				# Original Total periods = fb_row.total_number_of_depreciations (This was UPDATED in update_asset!)
				# So remaining periods = Total (Updated) - Covered (Preserved).
				
				remaining_periods = flt(fb_row.total_number_of_depreciations) - periods_covered
				
				if straddle_row_idx != -1:
					remaining_periods += 1
				
				# Generate new rows
				new_rows = []
				start_date = preserved_rows[-1].schedule_date if preserved_rows else asset.available_for_use_date
				
				# Generate
				# We can loop manually to avoid complexity of `make_depr_schedule`
				
				final_value = flt(fb_row.expected_value_after_useful_life)
				# Depreciable Amount for the FUTURE section
				depreciable_amt = new_base_at_cutoff - final_value
				
				current_date = getdate(start_date)
				frequency_months = cint(fb_row.frequency_of_depreciation)
				
				# Rounding precision
				precision = asset.precision("gross_purchase_amount")
				
				accumulated_depr = pres_depr_sum
				
				# Phase 1: Generate Dates
				generated_dates = []
				for i in range(cint(remaining_periods)):
					if i == 0 and first_target_date:
						next_date = first_target_date
					else:
						next_date = add_months(current_date, frequency_months)
						if is_last_day_of_the_month(current_date):
							next_date = get_last_day(next_date)
					
					generated_dates.append(next_date)
					current_date = next_date
				
				# Phase 2: Calculate Total Days
				total_days_remaining = 0
				
				# CORRECT DAY COUNTING
				# We must sum the days of each interval.
				# Interval 1: Start -> Date[0]
				# Interval 2: Date[0] -> Date[1]
				# ...
				
				temp_start = getdate(start_date)
				if generated_dates:
					total_duration_days = date_diff(generated_dates[-1], temp_start)
				else:
					total_duration_days = 0

				daily_rate = 0
				if total_duration_days > 0:
					daily_rate = depreciable_amt / total_duration_days
				
				# Pre-map existing Journal Entries by Date to preserve them
				booked_je_map = {}
				for r in original_rows:
					if r.journal_entry:
						 booked_je_map[getdate(r.schedule_date)] = r.journal_entry

				# Phase 3: Create Rows
				current_start = getdate(start_date)
				for i, date_val in enumerate(generated_dates):
					days = date_diff(date_val, current_start)
					d_amt = flt(daily_rate * days, precision)
					
					# Adjust last row
					if i == len(generated_dates) - 1:
						# Balance
						current_val_before = new_base_at_cutoff - (flt(accumulated_depr) - pres_depr_sum)
						d_amt = current_val_before - final_value
						d_amt = flt(d_amt, precision)
					
					accumulated_depr += d_amt
					
					# Check if this date was previously booked
					# If so, restore the JE link and preserve its specific date match if needed
					existing_je = booked_je_map.get(getdate(date_val), "")

					new_rows.append({
						"schedule_date": date_val,
						"depreciation_amount": d_amt,
						"accumulated_depreciation_amount": flt(accumulated_depr, precision),
						"journal_entry": existing_je
					})
					current_start = date_val

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
def get_asset_details(asset, revaluation_date=None):
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
		cond = ""
		if revaluation_date:
			cond = f"and schedule_date < '{revaluation_date}'"

		accumulated_depreciation = frappe.db.sql(f"""
			select sum(depreciation_amount) 
			from `tabDepreciation Schedule` 
			where parent=%s and parenttype='Asset' and docstatus=1 {cond}
		""", asset)[0][0] or 0.0
		
		return {
			"company": asset_doc.company,
			"original_cost": asset_doc.total_asset_cost,
			"accumulated_depreciation": accumulated_depreciation,
			"net_book_value": flt(asset_doc.total_asset_cost) - flt(accumulated_depreciation),
			"current_asset_value": flt(asset_doc.total_asset_cost) - flt(accumulated_depreciation),
			"depreciation_method": "",
			"total_useful_life": 0,
			"remaining_useful_life": 0,
			"remaining_useful_life_months": 0
		}

	# Calculate Useful Life
	total_months = flt(fb_row.total_number_of_depreciations) * flt(fb_row.frequency_of_depreciation)
	useful_life_years = total_months / 12.0
	
	# Calculate Accumulated Depreciation
	# We sum the depreciation amounts from the schedule (booked ones) to allow for revaluations (appreciation)
	# without causing negative accumulated depreciation.
	# "Accumulated Depreciation" should strictly be "Amount written off".
	
	# 1. Calculate Booked Accumulated Depreciation (Static / Current State)
	accumulated_depreciation = frappe.db.sql("""
		select sum(ds.depreciation_amount) 
		from `tabAsset Depreciation Schedule` ads 
		join `tabDepreciation Schedule` ds on ds.parent = ads.name
		where ads.asset=%s and ads.finance_book=%s and ads.status='Active'
		and ds.journal_entry is not null and ds.journal_entry != ''
	""", (asset_doc.name, fb_row.finance_book))[0][0] or 0.0
	
	# 2. Calculate Projected Value at Revaluation Date (Dynamic)
	# We use the schedule to find what the value WOULD be at the revaluation date
	# (Cost - Depreciation scheduled up to that date).
	
	cond = ""
	if revaluation_date:
		cond = f"and ds.schedule_date < '{revaluation_date}'"
	else:
		cond = f"and ds.schedule_date < '{nowdate()}'"

	projected_accum_depr = frappe.db.sql(f"""
		select sum(ds.depreciation_amount) 
		from `tabAsset Depreciation Schedule` ads 
		join `tabDepreciation Schedule` ds on ds.parent = ads.name
		where ads.asset=%s and ads.finance_book=%s and ads.status='Active'
		{cond}
	""", (asset_doc.name, fb_row.finance_book))[0][0] or 0.0
	
	current_asset_value = flt(asset_doc.total_asset_cost) - flt(projected_accum_depr)
	
	# Maintain original return structure for other fields
	value_after_depr = flt(fb_row.value_after_depreciation)
	nbv = value_after_depr # Default logic returned this
	
	# But for the new field, we use our calculated one
	
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
		"current_asset_value": current_asset_value,
		"remaining_useful_life": remaining_years,
		"remaining_useful_life_months": remaining_months
	}
