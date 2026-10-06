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
			"label": _("Breakdown No"),
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Meat Breakdown",
			"width": 140
		},
		{
			"label": _("Date"),
			"fieldname": "posting_date",
			"fieldtype": "Date",
			"width": 100
		},
		{
			"label": _("Template"),
			"fieldname": "template",
			"fieldtype": "Link",
			"options": "Meat Breakdown Template",
			"width": 160
		},
		{
			"label": _("Carcass Item"),
			"fieldname": "carcass_item",
			"fieldtype": "Link",
			"options": "Item",
			"width": 140
		},
		{
			"label": _("Source Batch"),
			"fieldname": "source_batch_no",
			"fieldtype": "Data",
			"width": 130
		},
		{
			"label": _("Warehouse"),
			"fieldname": "source_warehouse",
			"fieldtype": "Link",
			"options": "Warehouse",
			"width": 130
		},
		{
			"label": _("Input Weight (kg)"),
			"fieldname": "source_carcass_weight",
			"fieldtype": "Float",
			"width": 120
		},
		{
			"label": _("Outturn Cuts (kg)"),
			"fieldname": "total_outturn_weight",
			"fieldtype": "Float",
			"width": 120
		},
		{
			"label": _("Cutting Loss (kg)"),
			"fieldname": "cutting_loss_weight",
			"fieldtype": "Float",
			"width": 120
		},
		{
			"label": _("Cutting Loss %"),
			"fieldname": "cutting_loss_pct",
			"fieldtype": "Percent",
			"width": 110
		},
		{
			"label": _("Carcass Cost"),
			"fieldname": "total_carcass_cost",
			"fieldtype": "Currency",
			"width": 120
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
	if filters.get("template"):
		conditions.append("template = %(template)s")
		values["template"] = filters["template"]
	if filters.get("warehouse"):
		conditions.append("source_warehouse = %(warehouse)s")
		values["warehouse"] = filters["warehouse"]

	where_str = ("WHERE " + " AND ".join(conditions)) if conditions else ""

	query = f"""
		SELECT
			name, posting_date, template, carcass_item,
			source_batch_no, source_warehouse, source_carcass_weight,
			total_outturn_weight, cutting_loss_weight, cutting_loss_pct,
			total_carcass_cost, stock_entry, status
		FROM
			`tabMeat Breakdown`
		{where_str}
		ORDER BY
			posting_date DESC, creation DESC
	"""

	return frappe.db.sql(query, values, as_dict=True)

def get_chart_data(data):
	if not data:
		return None

	labels = []
	losses = []
	for row in data[:10]:
		labels.append(row.get("name"))
		losses.append(flt(row.get("cutting_loss_pct")))

	return {
		"data": {
			"labels": labels,
			"datasets": [
				{"name": _("Cutting Loss %"), "values": losses}
			]
		},
		"type": "bar",
		"colors": ["#f39c12"]
	}
