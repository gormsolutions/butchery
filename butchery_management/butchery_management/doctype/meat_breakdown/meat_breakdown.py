# Copyright (c) 2026, Tumel and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, nowtime


class MeatBreakdown(Document):
	def validate(self):
		self.calculate_mass_balance_and_nrv()
		self.check_loss_threshold()
		self.set_child_batches()

	def calculate_mass_balance_and_nrv(self):
		in_wt = flt(self.source_carcass_weight)
		in_rate = flt(self.carcass_valuation_rate)

		if in_wt <= 0:
			frappe.throw(_("Input Carcass Weight must be greater than 0."))
		if in_rate <= 0:
			frappe.throw(_("Carcass Valuation Rate per kg must be greater than 0."))

		self.total_carcass_cost = round(in_wt * in_rate, 2)

		# 1. Mass balance
		total_outturn = 0.0
		total_sales_val = 0.0

		for cut in self.cuts:
			c_wt = flt(cut.actual_weight)
			c_price = flt(cut.standard_selling_price)

			if c_wt < 0:
				frappe.throw(_("Actual weight for cut {0} cannot be negative.").format(cut.item_code))

			cut.actual_yield_pct = round((c_wt / in_wt) * 100.0, 2) if in_wt else 0.0
			cut.sales_value = round(c_wt * c_price, 2)

			total_outturn += c_wt
			total_sales_val += cut.sales_value

		self.total_outturn_weight = round(total_outturn, 3)
		self.cutting_loss_weight = round(in_wt - total_outturn, 3)
		self.cutting_loss_pct = round((self.cutting_loss_weight / in_wt) * 100.0, 2) if in_wt else 0.0
		self.net_yield_pct = round((total_outturn / in_wt) * 100.0, 2) if in_wt else 0.0
		self.total_sales_value = round(total_sales_val, 2)

		if self.total_outturn_weight > (in_wt * 1.05):
			frappe.throw(
				_("Total outturn cuts weight ({0}kg) exceeds input carcass weight ({1}kg) by more than 5%. Please re-check scale readings.").format(
					self.total_outturn_weight, in_wt
				)
			)

		# 2. Net Realizable Value (NRV) Cost Allocation
		for cut in self.cuts:
			c_wt = flt(cut.actual_weight)
			if total_sales_val > 0 and c_wt > 0:
				cut.sales_value_ratio = round((cut.sales_value / total_sales_val) * 100.0, 2)
				cut.allocated_cost = round(self.total_carcass_cost * (cut.sales_value / total_sales_val), 2)
				cut.cost_per_kg = round(cut.allocated_cost / c_wt, 2)
			else:
				cut.sales_value_ratio = 0.0
				cut.allocated_cost = 0.0
				cut.cost_per_kg = 0.0

	def check_loss_threshold(self):
		max_loss = frappe.db.get_single_value("Butchery Settings", "max_allowable_cutting_loss_pct") or 3.0
		if self.cutting_loss_pct > flt(max_loss):
			frappe.msgprint(
				_("⚠️ Warning: Carcass cutting loss is {0}%, which exceeds the allowable threshold of {1}%. "
				  "Unaccounted loss: {2}kg.").format(
					self.cutting_loss_pct, max_loss, self.cutting_loss_weight
				),
				indicator="orange"
			)

	def set_child_batches(self):
		prefix = (self.source_batch_no or self.name).strip()
		used_prefixes = set()

		for cut in self.cuts:
			if not cut.batch_no:
				words = cut.item_code.replace("(", "").replace(")", "").split()
				if len(words) == 1:
					candidate = words[0][:5].upper()
				elif len(words) >= 2:
					candidate = (words[0][:2] + words[1][:3]).upper()
				else:
					candidate = cut.item_code[:5].upper()

				if candidate in used_prefixes:
					suffix = 2
					while f"{candidate[:4]}{suffix}" in used_prefixes:
						suffix += 1
					candidate = f"{candidate[:4]}{suffix}"

				used_prefixes.add(candidate)
				cut.batch_no = f"{candidate}-{prefix}"

	def on_submit(self):
		self.create_child_batches_if_needed()
		self.create_stock_entry()
		self.db_set("status", "Submitted")

	def on_cancel(self):
		if self.stock_entry:
			se = frappe.get_doc("Stock Entry", self.stock_entry)
			if se.docstatus == 1:
				se.cancel()
		self.db_set("status", "Cancelled")

	def create_child_batches_if_needed(self):
		for cut in self.cuts:
			if cut.batch_no:
				has_batch = frappe.db.get_value("Item", cut.item_code, "has_batch_no")
				if has_batch and not frappe.db.exists("Batch", cut.batch_no):
					b = frappe.get_doc({
						"doctype": "Batch",
						"batch_id": cut.batch_no,
						"item": cut.item_code,
						"description": f"Deboned from Carcass {self.carcass_item} ({self.source_batch_no}) on {self.posting_date}"
					})
					b.insert(ignore_permissions=True)

	def create_stock_entry(self):
		"""Generates and submits a native ERPNext Repack Stock Entry"""
		se = frappe.new_doc("Stock Entry")
		se.purpose = "Repack"
		se.stock_entry_type = "Repack"
		se.company = self.company
		se.posting_date = self.posting_date
		se.posting_time = self.posting_time or nowtime()

		carcass_has_batch = frappe.db.get_value("Item", self.carcass_item, "has_batch_no")
		carcass_uom = frappe.db.get_value("Item", self.carcass_item, "stock_uom") or "Kg"

		# Source row (Carcass deduction)
		source_row = {
			"s_warehouse": self.source_warehouse,
			"item_code": self.carcass_item,
			"qty": self.source_carcass_weight,
			"basic_rate": self.carcass_valuation_rate,
			"uom": carcass_uom,
			"conversion_factor": 1.0
		}
		if carcass_has_batch and self.source_batch_no:
			bundle = frappe.get_doc({
				"doctype": "Serial and Batch Bundle",
				"company": self.company,
				"item_code": self.carcass_item,
				"warehouse": self.source_warehouse,
				"voucher_type": "Stock Entry",
				"type_of_transaction": "Outward",
				"posting_date": self.posting_date,
				"posting_time": self.posting_time or nowtime(),
				"qty": -1 * flt(self.source_carcass_weight),
				"entries": [
					{"batch_no": self.source_batch_no, "qty": -1 * flt(self.source_carcass_weight)}
				]
			})
			bundle.insert(ignore_permissions=True)
			source_row["serial_and_batch_bundle"] = bundle.name
		se.append("items", source_row)

		# Target rows (Cuts receipt)
		for cut in self.cuts:
			if flt(cut.actual_weight) <= 0:
				continue

			cut_has_batch = frappe.db.get_value("Item", cut.item_code, "has_batch_no")
			cut_uom = frappe.db.get_value("Item", cut.item_code, "stock_uom") or "Kg"

			t_row = {
				"t_warehouse": self.target_warehouse,
				"item_code": cut.item_code,
				"qty": cut.actual_weight,
				"basic_rate": cut.cost_per_kg,
				"set_basic_rate_manually": 1,
				"uom": cut_uom,
				"conversion_factor": 1.0
			}
			if cut_has_batch and cut.batch_no:
				t_row["batch_no"] = cut.batch_no

			se.append("items", t_row)

		se.remarks = (
			f"Generated via Meat Breakdown {self.name} for Carcass {self.carcass_item} ({self.source_batch_no}). "
			f"Input: {self.source_carcass_weight}kg, Outturn: {self.total_outturn_weight}kg, "
			f"Cutting Loss: {self.cutting_loss_weight}kg ({self.cutting_loss_pct}%)."
		)

		se.insert(ignore_permissions=True)
		se.submit()
		self.db_set("stock_entry", se.name)


@frappe.whitelist()
def get_template_cuts(template_name):
	"""Returns pre-configured cut list from template for 1-click floor entry"""
	if not template_name:
		return []

	template = frappe.get_doc("Meat Breakdown Template", template_name)
	cuts = []
	for item in template.items:
		cuts.append({
			"item_code": item.item_code,
			"item_name": item.item_name,
			"meat_cut_category": item.meat_cut_category,
			"expected_yield_pct": item.expected_yield_pct,
			"standard_selling_price": item.standard_selling_price,
			"actual_weight": 0.0
		})
	return cuts
