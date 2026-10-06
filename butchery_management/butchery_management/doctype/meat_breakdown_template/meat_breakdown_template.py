# Copyright (c) 2026, Tumel and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class MeatBreakdownTemplate(Document):
	def validate(self):
		self.calculate_totals()

	def calculate_totals(self):
		total_yield = 0.0
		for item in self.items:
			total_yield += float(item.expected_yield_pct or 0.0)
		self.total_expected_yield_pct = round(total_yield, 2)
