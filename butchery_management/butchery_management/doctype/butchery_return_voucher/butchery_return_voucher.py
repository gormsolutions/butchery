# Copyright (c) 2026, Tumel and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, nowtime


class ButcheryReturnVoucher(Document):
	def validate(self):
		self.calculate_variance()

	def calculate_variance(self):
		rej_wt = flt(self.customer_rejected_weight)
		rec_wt = flt(self.actual_store_received_weight)
		rate = flt(self.item_valuation_rate)

		if rej_wt <= 0:
			frappe.throw(_("Customer Rejected Weight must be greater than 0."))
		if rec_wt <= 0:
			frappe.throw(_("Actual Store Received Weight must be greater than 0."))

		if rec_wt > (rej_wt * 1.05):
			frappe.throw(_("Actual Store Received Weight ({0}kg) cannot exceed Customer Rejected Weight ({1}kg).").format(rec_wt, rej_wt))

		self.return_transit_loss = round(rej_wt - rec_wt, 3)
		self.loss_pct = round((self.return_transit_loss / rej_wt) * 100.0, 2) if rej_wt else 0.0
		self.loss_amount = round(self.return_transit_loss * rate, 2)

		if self.loss_pct > 2.0:
			frappe.msgprint(
				_("⚠️ High return transit shortage ({0}%). Driver: {1}, Customer: {2}").format(
					self.loss_pct, self.driver_rider or _("Unknown"), self.customer
				),
				indicator="orange"
			)

	def on_submit(self):
		self.create_stock_entry()
		self.db_set("status", "Submitted")

	def on_cancel(self):
		if self.stock_entry:
			se = frappe.get_doc("Stock Entry", self.stock_entry)
			if se.docstatus == 1:
				se.cancel()
		self.db_set("status", "Cancelled")

	def create_stock_entry(self):
		"""Restocks the actual physical weight received into warehouse"""
		se = frappe.new_doc("Stock Entry")
		se.purpose = "Material Receipt"
		se.stock_entry_type = "Material Receipt"
		se.company = self.company
		se.posting_date = self.posting_date
		se.posting_time = self.posting_time or nowtime()

		item_has_batch = frappe.db.get_value("Item", self.item_code, "has_batch_no")
		item_uom = frappe.db.get_value("Item", self.item_code, "stock_uom") or "Kg"

		row = {
			"item_code": self.item_code,
			"t_warehouse": self.return_warehouse,
			"qty": self.actual_store_received_weight,
			"basic_rate": self.item_valuation_rate,
			"uom": item_uom,
			"conversion_factor": 1.0
		}
		if item_has_batch:
			if not self.batch_no:
				batch_id = f"RET-{self.name}"
				if not frappe.db.exists("Batch", {"batch_id": batch_id, "item": self.item_code}):
					b = frappe.get_doc({
						"doctype": "Batch",
						"batch_id": batch_id,
						"item": self.item_code,
						"description": f"Restocked via Return Voucher {self.name} from {self.customer}"
					})
					b.insert(ignore_permissions=True)
				self.db_set("batch_no", batch_id)
				row["batch_no"] = batch_id
			else:
				row["batch_no"] = self.batch_no

		se.append("items", row)

		se.remarks = (
			f"Generated via Butchery Return Voucher {self.name} for Customer {self.customer} (DN: {self.delivery_note}). "
			f"Customer Rejected: {self.customer_rejected_weight}kg, Actual Restocked: {self.actual_store_received_weight}kg, "
			f"Return Transit Shortage: {self.return_transit_loss}kg ({self.loss_pct}%), Driver: {self.driver_rider}."
		)

		se.insert(ignore_permissions=True)
		se.submit()
		self.db_set("stock_entry", se.name)
