# Copyright (c) 2026, Tumel and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, nowtime


class ButcheryReceivingVoucher(Document):
	def validate(self):
		self.calculate_weights_and_valuation()
		self.check_loss_threshold()

	def calculate_weights_and_valuation(self):
		inv_wt = flt(self.invoiced_weight)
		inv_rate = flt(self.invoiced_rate_per_kg)
		rec_wt = flt(self.received_weight)

		if inv_wt <= 0:
			frappe.throw(_("Supplier Invoiced Weight must be greater than 0."))
		if rec_wt <= 0:
			frappe.throw(_("Actual Received Weight must be greater than 0."))

		self.invoiced_amount = round(inv_wt * inv_rate, 2)
		self.weight_variance = round(inv_wt - rec_wt, 3)
		self.variance_pct = round((self.weight_variance / inv_wt) * 100.0, 2) if inv_wt else 0.0
		self.variance_amount = round(self.weight_variance * inv_rate, 2)

		# Effective valuation rate entering stock ledger
		if self.shortage_treatment == "Absorb in Valuation (Capitalize Loss)":
			self.effective_valuation_rate = round(self.invoiced_amount / rec_wt, 2) if rec_wt else inv_rate
		else:
			self.effective_valuation_rate = inv_rate

	def check_loss_threshold(self):
		max_allowed = frappe.db.get_single_value("Butchery Settings", "max_allowable_transit_loss_pct") or 2.0
		if self.variance_pct > flt(max_allowed):
			frappe.msgprint(
				_("⚠️ Warning: Transit shortage is {0}%, exceeding the allowed threshold of {1}%. "
				  "Dispatcher: {2}, Supplier: {3}").format(
					self.variance_pct, max_allowed, self.dispatcher_name or _("Unknown"), self.supplier
				),
				indicator="orange"
			)

	def on_submit(self):
		self.create_or_get_batch()
		self.create_stock_entry()
		self.db_set("status", "Submitted")

	def on_cancel(self):
		if self.stock_entry:
			se = frappe.get_doc("Stock Entry", self.stock_entry)
			if se.docstatus == 1:
				se.cancel()
		self.db_set("status", "Cancelled")

	def create_or_get_batch(self):
		if not self.batch_no:
			frappe.throw(_("Animal / Carcass Batch No is required."))

		item_has_batch = frappe.db.get_value("Item", self.carcass_item, "has_batch_no")
		if item_has_batch:
			if not frappe.db.exists("Batch", {"batch_id": self.batch_no, "item": self.carcass_item}):
				batch = frappe.get_doc({
					"doctype": "Batch",
					"batch_id": self.batch_no,
					"item": self.carcass_item,
					"description": f"Received from {self.supplier} on {self.posting_date} ({self.received_weight}kg)"
				})
				batch.insert(ignore_permissions=True)

	def create_stock_entry(self):
		"""Creates and submits a native ERPNext Material Receipt Stock Entry"""
		se = frappe.new_doc("Stock Entry")
		se.purpose = "Material Receipt"
		se.stock_entry_type = "Material Receipt"
		se.company = self.company
		se.posting_date = self.posting_date
		se.posting_time = self.posting_time or nowtime()

		item_has_batch = frappe.db.get_value("Item", self.carcass_item, "has_batch_no")

		row = {
			"item_code": self.carcass_item,
			"t_warehouse": self.receiving_outlet,
			"qty": self.received_weight,
			"basic_rate": self.effective_valuation_rate,
			"uom": frappe.db.get_value("Item", self.carcass_item, "stock_uom") or "Kg",
			"conversion_factor": 1.0
		}
		if item_has_batch:
			row["batch_no"] = self.batch_no

		se.append("items", row)
		se.remarks = (
			f"Generated via Butchery Receiving Voucher {self.name} from {self.supplier}. "
			f"Invoiced: {self.invoiced_weight}kg, Received: {self.received_weight}kg, "
			f"Transit Loss: {self.weight_variance}kg ({self.variance_pct}%)."
		)

		se.insert(ignore_permissions=True)
		se.submit()
		self.db_set("stock_entry", se.name)
