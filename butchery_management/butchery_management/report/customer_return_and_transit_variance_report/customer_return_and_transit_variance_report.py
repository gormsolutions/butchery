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
			"label": _("Return Voucher"),
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Butchery Return Voucher",
			"width": 140
		},
		{
			"label": _("Date"),
			"fieldname": "posting_date",
			"fieldtype": "Date",
			"width": 100
		},
		{
			"label": _("Customer"),
			"fieldname": "customer",
			"fieldtype": "Link",
			"options": "Customer",
			"width": 150
		},
		{
			"label": _("Delivery Note"),
			"fieldname": "delivery_note",
			"fieldtype": "Link",
			"options": "Delivery Note",
			"width": 130
		},
		{
			"label": _("Driver / Rider"),
			"fieldname": "driver_rider",
			"fieldtype": "Data",
			"width": 130
		},
		{
			"label": _("Vehicle No"),
			"fieldname": "vehicle_no",
			"fieldtype": "Data",
			"width": 100
		},
		{
			"label": _("Item"),
			"fieldname": "item_code",
			"fieldtype": "Link",
			"options": "Item",
			"width": 130
		},
		{
			"label": _("Dispatched (kg)"),
			"fieldname": "dispatched_weight",
			"fieldtype": "Float",
			"width": 110
		},
		{
			"label": _("Cust Rejected (kg)"),
			"fieldname": "customer_rejected_weight",
			"fieldtype": "Float",
			"width": 120
		},
		{
			"label": _("Store Received (kg)"),
			"fieldname": "actual_store_received_weight",
			"fieldtype": "Float",
			"width": 120
		},
		{
			"label": _("Transit Loss (kg)"),
			"fieldname": "return_transit_loss",
			"fieldtype": "Float",
			"width": 110
		},
		{
			"label": _("Loss %"),
			"fieldname": "loss_pct",
			"fieldtype": "Percent",
			"width": 90
		},
		{
			"label": _("Loss Amount"),
			"fieldname": "loss_amount",
			"fieldtype": "Currency",
			"width": 110
		},
		{
			"label": _("Restocked Batch"),
			"fieldname": "batch_no",
			"fieldtype": "Link",
			"options": "Batch",
			"width": 130
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
	if filters.get("customer"):
		conditions.append("customer = %(customer)s")
		values["customer"] = filters["customer"]
	if filters.get("driver_rider"):
		conditions.append("driver_rider LIKE %(driver_rider)s")
		values["driver_rider"] = f"%{filters['driver_rider']}%"

	where_str = ("WHERE " + " AND ".join(conditions)) if conditions else ""

	query = f"""
		SELECT
			name, posting_date, customer, delivery_note, driver_rider,
			vehicle_no, item_code, dispatched_weight, customer_rejected_weight,
			actual_store_received_weight, return_transit_loss, loss_pct,
			loss_amount, batch_no, stock_entry, status
		FROM
			`tabButchery Return Voucher`
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
		losses.append(flt(row.get("return_transit_loss")))

	return {
		"data": {
			"labels": labels,
			"datasets": [
				{"name": _("Transit Loss (kg)"), "values": losses}
			]
		},
		"type": "bar",
		"colors": ["#e74c3c"]
	}
