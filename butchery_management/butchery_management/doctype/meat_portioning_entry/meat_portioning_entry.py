# Copyright (c) 2026, Tumel and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, flt, nowtime


class MeatPortioningEntry(Document):
	def validate(self):
		self.calculate_portioning()
		self.set_expiry_and_barcode()

	def calculate_portioning(self):
		wt = flt(self.bulk_weight_used)
		rate = flt(self.bulk_valuation_rate)
		packs = int(self.packs_produced or 0)

		if wt <= 0:
			frappe.throw(_("Bulk Weight Used must be greater than 0."))
		if packs <= 0:
			frappe.throw(_("Packs Produced must be greater than 0."))

		self.bulk_meat_cost = round(wt * rate, 2)

		# Packaging materials cost
		pack_cost = 0.0
		for row in (self.packaging_materials or []):
			q = flt(row.qty)
			item_rate = flt(frappe.db.get_value("Item", row.item_code, "valuation_rate") or 0.0)
			pack_cost += q * item_rate

		self.total_packaging_cost = round(pack_cost, 2)
		self.total_production_cost = round(self.bulk_meat_cost + self.total_packaging_cost, 2)
		self.cost_per_pack = round(self.total_production_cost / packs, 2) if packs else 0.0

	def set_expiry_and_barcode(self):
		days = int(self.shelf_life_days or 14)
		self.expiry_date = add_days(self.posting_date, days)

		if not self.retail_batch_no:
			src_tag = self.bulk_batch_no or self.name
			self.retail_batch_no = f"PK-{src_tag}"

		if not self.barcode:
			item_clean = self.retail_item.replace(" ", "").upper()[:4]
			self.barcode = f"20{item_clean}{str(self.packs_produced).zfill(4)}"

	def on_submit(self):
		self.create_retail_batch_if_needed()
		self.create_stock_entry()
		self.db_set("status", "Submitted")

	def on_cancel(self):
		if self.stock_entry:
			se = frappe.get_doc("Stock Entry", self.stock_entry)
			if se.docstatus == 1:
				se.cancel()
		self.db_set("status", "Cancelled")

	def create_retail_batch_if_needed(self):
		has_batch = frappe.db.get_value("Item", self.retail_item, "has_batch_no")
		if has_batch and self.retail_batch_no:
			if not frappe.db.exists("Batch", {"batch_id": self.retail_batch_no, "item": self.retail_item}):
				b = frappe.get_doc({
					"doctype": "Batch",
					"batch_id": self.retail_batch_no,
					"item": self.retail_item,
					"expiry_date": self.expiry_date,
					"description": f"Portioned from {self.bulk_item} ({self.bulk_batch_no}) on {self.posting_date}"
				})
				b.insert(ignore_permissions=True)

	def create_stock_entry(self):
		se = frappe.new_doc("Stock Entry")
		se.purpose = "Repack"
		se.stock_entry_type = "Repack"
		se.company = self.company
		se.posting_date = self.posting_date
		se.posting_time = self.posting_time or nowtime()

		b_has_batch = frappe.db.get_value("Item", self.bulk_item, "has_batch_no")
		b_uom = frappe.db.get_value("Item", self.bulk_item, "stock_uom") or "Kg"

		r_has_batch = frappe.db.get_value("Item", self.retail_item, "has_batch_no")
		r_uom = frappe.db.get_value("Item", self.retail_item, "stock_uom") or "Pack"

		# Source row (bulk meat)
		s_row = {
			"s_warehouse": self.warehouse,
			"item_code": self.bulk_item,
			"qty": self.bulk_weight_used,
			"basic_rate": self.bulk_valuation_rate,
			"uom": b_uom,
			"conversion_factor": 1.0
		}
		if b_has_batch and self.bulk_batch_no:
			bundle = frappe.get_doc({
				"doctype": "Serial and Batch Bundle",
				"company": self.company,
				"item_code": self.bulk_item,
				"warehouse": self.warehouse,
				"voucher_type": "Stock Entry",
				"type_of_transaction": "Outward",
				"posting_date": self.posting_date,
				"posting_time": self.posting_time or nowtime(),
				"qty": -1 * flt(self.bulk_weight_used),
				"entries": [
					{"batch_no": self.bulk_batch_no, "qty": -1 * flt(self.bulk_weight_used)}
				]
			})
			bundle.insert(ignore_permissions=True)
			s_row["serial_and_batch_bundle"] = bundle.name
		se.append("items", s_row)

		# Packaging material source rows
		for pkg in (self.packaging_materials or []):
			pkg_rate = flt(frappe.db.get_value("Item", pkg.item_code, "valuation_rate") or 0.0)
			se.append("items", {
				"s_warehouse": self.warehouse,
				"item_code": pkg.item_code,
				"qty": pkg.qty,
				"basic_rate": pkg_rate,
				"uom": pkg.uom or "Nos",
				"conversion_factor": 1.0
			})

		# Target row (retail packs)
		t_row = {
			"t_warehouse": self.warehouse,
			"item_code": self.retail_item,
			"qty": self.packs_produced,
			"basic_rate": self.cost_per_pack,
			"set_basic_rate_manually": 1,
			"uom": r_uom,
			"conversion_factor": 1.0
		}
		if r_has_batch and self.retail_batch_no:
			t_row["batch_no"] = self.retail_batch_no
		se.append("items", t_row)

		se.remarks = (
			f"Generated via Meat Portioning Entry {self.name}. "
			f"Portioned {self.bulk_weight_used}kg of {self.bulk_item} into {self.packs_produced} packs of {self.retail_item}. "
			f"Unit Cost: {self.cost_per_pack}/pack, Expiry: {self.expiry_date}."
		)

		se.insert(ignore_permissions=True)
		se.submit()
		self.db_set("stock_entry", se.name)
