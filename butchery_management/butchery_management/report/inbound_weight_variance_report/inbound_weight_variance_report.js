// Copyright (c) 2026, Tumel and contributors
// For license information, please see license.txt

frappe.query_reports["Inbound Weight Variance Report"] = {
	"filters": [
		{
			"fieldname": "company",
			"label": __("Company"),
			"fieldtype": "Link",
			"options": "Company",
			"default": frappe.defaults.get_user_default("Company")
		},
		{
			"fieldname": "from_date",
			"label": __("From Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.add_months(frappe.datetime.get_today(), -1)
		},
		{
			"fieldname": "to_date",
			"label": __("To Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.get_today()
		},
		{
			"fieldname": "supplier",
			"label": __("Supplier"),
			"fieldtype": "Link",
			"options": "Supplier"
		},
		{
			"fieldname": "receiving_outlet",
			"label": __("Receiving Outlet"),
			"fieldtype": "Link",
			"options": "Warehouse"
		},
		{
			"fieldname": "dispatcher_name",
			"label": __("Dispatcher / Logistics"),
			"fieldtype": "Data"
		}
	]
};
