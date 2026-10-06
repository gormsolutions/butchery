# Copyright (c) 2026, Tumel and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt

def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	chart = get_chart_data(data)
	return columns, data, None, chart

def get_columns():
	return [
		{
			"label": _("Voucher No"),
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Butchery Receiving Voucher",
			"width": 140
		},
		{
			"label": _("Date"),
			"fieldname": "posting_date",
			"fieldtype": "Date",
			"width": 100
		},
		{
			"label": _("Supplier"),
			"fieldname": "supplier",
			"fieldtype": "Link",
			"options": "Supplier",
			"width": 140
		},
		{
			"label": _("Dispatcher"),
			"fieldname": "dispatcher_name",
			"fieldtype": "Data",
			"width": 120
		},
		{
			"label": _("Vehicle No"),
			"fieldname": "vehicle_no",
			"fieldtype": "Data",
			"width": 100
		},
		{
			"label": _("Receiving Outlet"),
			"fieldname": "receiving_outlet",
			"fieldtype": "Link",
			"options": "Warehouse",
			"width": 130
		},
		{
			"label": _("Carcass Item"),
			"fieldname": "carcass_item",
			"fieldtype": "Link",
			"options": "Item",
			"width": 130
		},
		{
			"label": _("Invoiced (kg)"),
			"fieldname": "invoiced_weight",
			"fieldtype": "Float",
			"width": 110
		},
		{
			"label": _("Invoiced Rate"),
			"fieldname": "invoiced_rate_per_kg",
			"fieldtype": "Currency",
			"width": 110
		},
		{
			"label": _("Invoiced Amount"),
			"fieldname": "invoiced_amount",
			"fieldtype": "Currency",
			"width": 120
		},
		{
			"label": _("Received (kg)"),
			"fieldname": "received_weight",
			"fieldtype": "Float",
			"width": 110
		},
		{
			"label": _("Shortage (kg)"),
			"fieldname": "weight_variance",
			"fieldtype": "Float",
			"width": 110
		},
		{
			"label": _("Variance %"),
			"fieldname": "variance_pct",
			"fieldtype": "Percent",
			"width": 100
		},
		{
			"label": _("Treatment"),
			"fieldname": "shortage_treatment",
			"fieldtype": "Data",
			"width": 160
		},
		{
			"label": _("Effective Valuation/kg"),
			"fieldname": "effective_valuation_rate",
			"fieldtype": "Currency",
			"width": 140
		},
		{
			"label": _("Stock Entry"),
			"fieldname": "stock_entry",
			"fieldtype": "Link",
			"options": "Stock Entry",
			"width": 130
		},
		{
			"label": _("Status"),
			"fieldname": "status",
			"fieldtype": "Data",
			"width": 90
		}
	]

def get_data(filters):
	conditions = []
	values = {}

	if filters.get("company"):
		conditions.append("company = %(company)s")
		values["company"] = filters["company"]
	if filters.get("from_date"):
		conditions.append("posting_date >= %(from_date)s")
		values["from_date"] = filters["from_date"]
	if filters.get("to_date"):
		conditions.append("posting_date <= %(to_date)s")
		values["to_date"] = filters["to_date"]
	if filters.get("supplier"):
		conditions.append("supplier = %(supplier)s")
		values["supplier"] = filters["supplier"]
	if filters.get("dispatcher_name"):
		conditions.append("dispatcher_name LIKE %(dispatcher_name)s")
		values["dispatcher_name"] = f"%{filters['dispatcher_name']}%"
	if filters.get("receiving_outlet"):
		conditions.append("receiving_outlet = %(receiving_outlet)s")
		values["receiving_outlet"] = filters["receiving_outlet"]

	where_str = ("WHERE " + " AND ".join(conditions)) if conditions else ""

	query = f"""
		SELECT
			name, posting_date, supplier, dispatcher_name, vehicle_no,
			receiving_outlet, carcass_item, invoiced_weight, invoiced_rate_per_kg,
			invoiced_amount, received_weight, weight_variance, variance_pct,
			shortage_treatment, effective_valuation_rate, stock_entry, status
		FROM
			`tabButchery Receiving Voucher`
		{where_str}
		ORDER BY
			posting_date DESC, creation DESC
	"""

	return frappe.db.sql(query, values, as_dict=True)

def get_chart_data(data):
	if not data:
		return None

	labels = []
	shortages = []
	for row in data[:10]:
		labels.append(row.get("name"))
		shortages.append(flt(row.get("weight_variance")))

	return {
		"data": {
			"labels": labels,
			"datasets": [
				{"name": _("Shortage (kg)"), "values": shortages}
			]
		},
		"type": "bar",
		"colors": ["#e74c3c"]
	}
