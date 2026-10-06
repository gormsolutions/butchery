# Copyright (c) 2026, Tumel and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, nowtime


class MeatConversion(Document):
	def validate(self):
		self.calculate_conversion()
		self.set_target_batch()

	def calculate_conversion(self):
		c_qty = flt(self.convert_qty)
		s_rate = flt(self.source_valuation_rate)
		t_qty = flt(self.target_qty)

		if c_qty <= 0:
			frappe.throw(_("Quantity to Convert must be greater than 0."))
		if s_rate <= 0:
			frappe.throw(_("Source Valuation Rate must be greater than 0."))
		if t_qty <= 0:
			frappe.throw(_("Actual Target Qty must be greater than 0."))

		if t_qty > (c_qty * 1.05):
			frappe.throw(_("Target produced quantity ({0}kg) cannot exceed source quantity ({1}kg) by more than 5%.").format(t_qty, c_qty))

		self.source_total_cost = round(c_qty * s_rate, 2)
		self.conversion_loss = round(c_qty - t_qty, 3)
		self.conversion_loss_pct = round((self.conversion_loss / c_qty) * 100.0, 2) if c_qty else 0.0

		if self.loss_treatment == "Absorb into Target Product Cost":
			self.target_valuation_rate = round(self.source_total_cost / t_qty, 2) if t_qty else s_rate
		else:
			self.target_valuation_rate = s_rate

	def set_target_batch(self):
		if not self.target_batch_no:
			prefix = (self.target_item[:4]).upper().replace(" ", "")
			src_tag = self.source_batch_no or self.name
			self.target_batch_no = f"{prefix}-{src_tag}"

	def on_submit(self):
		self.create_target_batch_if_needed()
		self.create_stock_entry()
		self.db_set("status", "Submitted")

	def on_cancel(self):
		if self.stock_entry:
			se = frappe.get_doc("Stock Entry", self.stock_entry)
			if se.docstatus == 1:
				se.cancel()
		self.db_set("status", "Cancelled")

	def create_target_batch_if_needed(self):
		has_batch = frappe.db.get_value("Item", self.target_item, "has_batch_no")
		if has_batch and self.target_batch_no:
			if not frappe.db.exists("Batch", {"batch_id": self.target_batch_no, "item": self.target_item}):
				b = frappe.get_doc({
					"doctype": "Batch",
					"batch_id": self.target_batch_no,
					"item": self.target_item,
					"description": f"Converted from {self.source_item} ({self.source_batch_no}) on {self.posting_date}"
				})
				b.insert(ignore_permissions=True)

	def create_stock_entry(self):
		se = frappe.new_doc("Stock Entry")
		se.purpose = "Repack"
		se.stock_entry_type = "Repack"
		se.company = self.company
		se.posting_date = self.posting_date
		se.posting_time = self.posting_time or nowtime()

		s_has_batch = frappe.db.get_value("Item", self.source_item, "has_batch_no")
		s_uom = frappe.db.get_value("Item", self.source_item, "stock_uom") or "Kg"

		t_has_batch = frappe.db.get_value("Item", self.target_item, "has_batch_no")
		t_uom = frappe.db.get_value("Item", self.target_item, "stock_uom") or "Kg"

		# Source row (deduction)
		s_row = {
			"s_warehouse": self.warehouse,
			"item_code": self.source_item,
			"qty": self.convert_qty,
			"basic_rate": self.source_valuation_rate,
			"uom": s_uom,
			"conversion_factor": 1.0
		}
		if s_has_batch and self.source_batch_no:
			bundle = frappe.get_doc({
				"doctype": "Serial and Batch Bundle",
				"company": self.company,
				"item_code": self.source_item,
				"warehouse": self.warehouse,
				"voucher_type": "Stock Entry",
				"type_of_transaction": "Outward",
				"posting_date": self.posting_date,
				"posting_time": self.posting_time or nowtime(),
				"qty": -1 * flt(self.convert_qty),
				"entries": [
					{"batch_no": self.source_batch_no, "qty": -1 * flt(self.convert_qty)}
				]
			})
			bundle.insert(ignore_permissions=True)
			s_row["serial_and_batch_bundle"] = bundle.name
		se.append("items", s_row)

		# Target row (addition)
		t_row = {
			"t_warehouse": self.warehouse,
			"item_code": self.target_item,
			"qty": self.target_qty,
			"basic_rate": self.target_valuation_rate,
			"set_basic_rate_manually": 1,
			"uom": t_uom,
			"conversion_factor": 1.0
		}
		if t_has_batch and self.target_batch_no:
			t_row["batch_no"] = self.target_batch_no
		se.append("items", t_row)

		se.remarks = (
			f"Generated via Meat Conversion {self.name}. "
			f"Converted {self.convert_qty}kg of {self.source_item} into {self.target_qty}kg of {self.target_item}. "
			f"Loss: {self.conversion_loss}kg ({self.conversion_loss_pct}%)."
		)

		se.insert(ignore_permissions=True)
		se.submit()
		self.db_set("stock_entry", se.name)
