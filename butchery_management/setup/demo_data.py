# Copyright (c) 2026, Tumel and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import add_days, flt, nowdate, nowtime


@frappe.whitelist()
def setup_demo_data(company_name="Naija Prime Meats Ltd", abbr="NPM", force=False):
	"""
	Complete end-to-end Nigerian Butchery demo data generator.
	Creates:
	1. Nigerian Company & Chart of Accounts / Warehouses
	2. Butchery Expense Accounts & System Settings
	3. Nigerian Abattoir Suppliers & Hospitality/Retail Customers
	4. Meat Items (Carcasses, Primal Steaks, Cuts, Nigerian Offals, Consumables, Pre-Packs)
	5. Nigerian Meat Breakdown Template with NRV Benchmark Selling Prices
	6. Initial Consumables Stock
	7. End-to-end Transaction Flow:
	   - Inbound Butchery Receiving Vouchers (with scale variance & transit shrinkage)
	   - Carcass Meat Breakdown (Inverse manufacturing with mass-balance & NRV costing)
	   - Meat Conversion (Boneless beef to minced beef with grinder loss)
	   - Meat Portioning Entries (Bulk meat to retail pre-packs with barcodes and shelf-life)
	   - Butchery Return Voucher (B2B return transit loss audit)
	"""
	print(f"--- Setting up Nigerian Butchery Demo Data for [{company_name}] ---")

	company = ensure_company(company_name, abbr)
	warehouses = ensure_warehouses(company)
	expense_accounts = ensure_accounts(company)
	configure_butchery_settings(expense_accounts)
	suppliers = ensure_suppliers()
	customers = ensure_customers()
	ensure_uoms()
	ensure_item_groups()
	items = ensure_items()
	template = ensure_breakdown_template(items)

	frappe.db.commit()

	# Check if transactions already exist for this company
	existing_brv = frappe.db.get_value("Butchery Receiving Voucher", {"company": company.name}, "name")
	if existing_brv and not force:
		print(f"Demo transactions already exist for {company.name} ({existing_brv}). Skipping transaction creation.")
		print("To re-run transaction creation, use force=True.")
		return {
			"status": "success",
			"company": company.name,
			"message": "Master data updated. Transactions already present."
		}

	# Ensure packaging consumables stock
	ensure_initial_packaging_stock(company, warehouses)

	# Execute full transaction lifecycle
	print("\n>>> Generating Inbound Receiving Vouchers...")
	rec_vouchers = generate_receiving_vouchers(company, warehouses, suppliers)

	print("\n>>> Generating Carcass Breakdown (Deboning & NRV)...")
	breakdowns = generate_meat_breakdown(company, warehouses, rec_vouchers, template)

	print("\n>>> Generating Meat Conversion...")
	conversions = generate_meat_conversions(company, warehouses, breakdowns)

	print("\n>>> Generating Meat Portioning Entries...")
	portionings = generate_portioning_entries(company, warehouses, breakdowns, conversions)

	print("\n>>> Generating Butchery Return Voucher...")
	returns = generate_return_vouchers(company, warehouses, customers)

	frappe.db.commit()
	print(f"\n[SUCCESS] Butchery demo data successfully generated and committed for {company.name}!")
	return {
		"status": "success",
		"company": company.name,
		"receiving_vouchers": [v.name for v in rec_vouchers],
		"meat_breakdowns": [b.name for b in breakdowns],
		"conversions": [c.name for c in conversions],
		"portionings": [p.name for p in portionings],
		"returns": [r.name for r in returns]
	}


def ensure_company(company_name, abbr):
	if frappe.db.exists("Company", company_name):
		print(f"Company {company_name} exists.")
		company = frappe.get_doc("Company", company_name)
		ensure_fiscal_year(company)
		return company

	print(f"Creating Nigerian company {company_name} ({abbr})...")
	doc = frappe.get_doc({
		"doctype": "Company",
		"company_name": company_name,
		"abbr": abbr,
		"country": "Nigeria",
		"default_currency": "NGN"
	})
	doc.insert(ignore_permissions=True)
	ensure_fiscal_year(doc)
	frappe.db.commit()
	return doc


def ensure_fiscal_year(company):
	year = nowdate().split("-")[0]
	if frappe.db.exists("Fiscal Year", year):
		fy = frappe.get_doc("Fiscal Year", year)
		if fy.companies and not any(c.company == company.name for c in fy.companies):
			fy.append("companies", {"company": company.name})
			fy.save(ignore_permissions=True)
			print(f"Added {company.name} to Fiscal Year {year}.")
	else:
		fy = frappe.get_doc({
			"doctype": "Fiscal Year",
			"year": year,
			"year_start_date": f"{year}-01-01",
			"year_end_date": f"{year}-12-31",
			"companies": [{"company": company.name}]
		})
		fy.insert(ignore_permissions=True)
		print(f"Created Fiscal Year {year} for {company.name}.")



def ensure_warehouses(company):
	abbr = company.abbr
	parent_warehouse = f"All Warehouses - {abbr}"
	if not frappe.db.exists("Warehouse", parent_warehouse):
		# Default fallback
		parent_wh = frappe.get_all("Warehouse", filters={"company": company.name, "is_group": 1}, limit=1)
		parent_warehouse = parent_wh[0].name if parent_wh else None

	required_warehouses = [
		("Inbound Dock & Receiving", "Receiving scale dock for inbound livestock & carcasses"),
		("Carcass Cold Room", "Cold storage chamber for whole and quartered carcasses"),
		("Deboning & Processing Floor", "Deboning, trimming, cutting and grinder processing floor"),
		("Retail Pre-Pack & Display Chiller", "Consumer-ready retail packages and POS chiller"),
		("Customer Returns Holding", "Dedicated holding cold room for customer rejections and returns")
	]

	warehouses = {}
	for name, desc in required_warehouses:
		full_name = f"{name} - {abbr}"
		if not frappe.db.exists("Warehouse", full_name):
			print(f"Creating Warehouse: {full_name}")
			wh = frappe.get_doc({
				"doctype": "Warehouse",
				"warehouse_name": name,
				"company": company.name,
				"parent_warehouse": parent_warehouse
			})
			wh.insert(ignore_permissions=True)
			warehouses[name] = full_name
		else:
			warehouses[name] = full_name

	return warehouses


def ensure_accounts(company):
	abbr = company.abbr
	parent_expense = f"Direct Expenses - {abbr}"
	if not frappe.db.exists("Account", parent_expense):
		parent_exp = frappe.get_all("Account", filters={"company": company.name, "root_type": "Expense", "is_group": 1}, limit=1)
		parent_expense = parent_exp[0].name if parent_exp else None

	required_accounts = [
		("Transit Shortage Expense", "Expense", "Direct Expense"),
		("Carcass Cutting & Processing Loss", "Expense", "Direct Expense"),
		("Customer Return Transit Shortage", "Expense", "Direct Expense")
	]

	accounts = {}
	for name, root_type, report_type in required_accounts:
		full_name = f"{name} - {abbr}"
		if not frappe.db.exists("Account", full_name):
			print(f"Creating Account: {full_name}")
			acc = frappe.get_doc({
				"doctype": "Account",
				"account_name": name,
				"company": company.name,
				"parent_account": parent_expense,
				"root_type": root_type,
				"account_currency": "NGN"
			})
			acc.insert(ignore_permissions=True)
			accounts[name] = full_name
		else:
			accounts[name] = full_name

	return accounts


def configure_butchery_settings(accounts):
	settings = frappe.get_single("Butchery Settings")
	settings.max_allowable_transit_loss_pct = 2.5
	settings.max_allowable_cutting_loss_pct = 3.5
	if "Transit Shortage Expense" in accounts:
		settings.default_transit_loss_account = accounts["Transit Shortage Expense"]
	if "Carcass Cutting & Processing Loss" in accounts:
		settings.default_cutting_loss_account = accounts["Carcass Cutting & Processing Loss"]
	if "Customer Return Transit Shortage" in accounts:
		settings.default_return_loss_account = accounts["Customer Return Transit Shortage"]

	settings.save(ignore_permissions=True)
	print("Configured Butchery Settings successfully.")


def ensure_suppliers():
	suppliers = [
		{"supplier_name": "Oko-Oba Abattoir Agege", "supplier_group": "Local"},
		{"supplier_name": "Kara Cattle Market Ogun-Lagos", "supplier_group": "Local"},
		{"supplier_name": "Ikorodu Livestock Hub", "supplier_group": "Local"}
	]
	out = {}
	for s in suppliers:
		name = s["supplier_name"]
		if not frappe.db.exists("Supplier", name):
			print(f"Creating Supplier: {name}")
			doc = frappe.get_doc({
				"doctype": "Supplier",
				"supplier_name": name,
				"supplier_group": s["supplier_group"],
				"supplier_type": "Company",
				"country": "Nigeria"
			})
			doc.insert(ignore_permissions=True)
		out[name] = name
	return out


def ensure_customers():
	customers = [
		{"customer_name": "Eko Hotel & Suites Victoria Island", "customer_group": "Commercial"},
		{"customer_name": "Radisson Blu Anchorage Hotel", "customer_group": "Commercial"},
		{"customer_name": "The Palms Supermarket Deli Lekki", "customer_group": "Commercial"},
		{"customer_name": "ChopLife Suya & BBQ Lounge", "customer_group": "Commercial"}
	]
	out = {}
	for c in customers:
		name = c["customer_name"]
		if not frappe.db.exists("Customer", name):
			print(f"Creating Customer: {name}")
			doc = frappe.get_doc({
				"doctype": "Customer",
				"customer_name": name,
				"customer_group": c["customer_group"],
				"customer_type": "Company",
				"territory": "All Territories"
			})
			doc.insert(ignore_permissions=True)
		out[name] = name
	return out


def ensure_uoms():
	for uom_name in ["Kg", "Nos", "Pack"]:
		if not frappe.db.exists("UOM", uom_name):
			print(f"Creating UOM: {uom_name}")
			u = frappe.get_doc({
				"doctype": "UOM",
				"uom_name": uom_name
			})
			u.insert(ignore_permissions=True)


def ensure_item_groups():
	if not frappe.db.exists("Item Group", "Meat & Butchery Products"):
		print("Creating Item Group: Meat & Butchery Products")
		ig = frappe.get_doc({
			"doctype": "Item Group",
			"item_group_name": "Meat & Butchery Products",
			"parent_item_group": "All Item Groups",
			"is_group": 0
		})
		ig.insert(ignore_permissions=True)


def ensure_items():
	items_data = [
		# 1. Carcasses
		{"item_code": "Whole Beef Carcass", "item_name": "Whole Beef Carcass", "stock_uom": "Kg", "has_batch_no": 1},
		{"item_code": "Goat Carcass", "item_name": "Whole Goat Carcass", "stock_uom": "Kg", "has_batch_no": 1},
		{"item_code": "Ram Carcass", "item_name": "Whole Ram Carcass", "stock_uom": "Kg", "has_batch_no": 1},

		# 2. Primal Cuts
		{"item_code": "Beef Fillet", "item_name": "Beef Fillet", "stock_uom": "Kg", "has_batch_no": 1},
		{"item_code": "Ribeye", "item_name": "Ribeye Steak Cut", "stock_uom": "Kg", "has_batch_no": 1},
		{"item_code": "Sirloin Beef", "item_name": "Sirloin Beef Cut", "stock_uom": "Kg", "has_batch_no": 1},
		{"item_code": "T-Bone", "item_name": "T-Bone Steak Cut", "stock_uom": "Kg", "has_batch_no": 1},
		{"item_code": "Tomahawk Beef", "item_name": "Tomahawk Beef Cut", "stock_uom": "Kg", "has_batch_no": 1},
		{"item_code": "Minute Steak", "item_name": "Minute Steak Cut", "stock_uom": "Kg", "has_batch_no": 1},

		# 3. Manufacturing & Table Cuts
		{"item_code": "Boneless Beef", "item_name": "Boneless Manufacturing Beef", "stock_uom": "Kg", "has_batch_no": 1},
		{"item_code": "Minced Beef", "item_name": "Fresh Ground Minced Beef", "stock_uom": "Kg", "has_batch_no": 1},
		{"item_code": "Beef Topside", "item_name": "Beef Topside", "stock_uom": "Kg", "has_batch_no": 1},
		{"item_code": "Silver Side Beef", "item_name": "Silver Side Beef", "stock_uom": "Kg", "has_batch_no": 1},
		{"item_code": "Beef Tonzo", "item_name": "Beef Tonzo", "stock_uom": "Kg", "has_batch_no": 1},
		{"item_code": "Stewing Pack", "item_name": "Beef Stewing Meat Pack", "stock_uom": "Kg", "has_batch_no": 1},
		{"item_code": "Beef Shin", "item_name": "Beef Shin", "stock_uom": "Kg", "has_batch_no": 1},
		{"item_code": "Shredded Beef", "item_name": "Shredded Beef", "stock_uom": "Kg", "has_batch_no": 1},
		{"item_code": "Beef Cube", "item_name": "Beef Cube Diced", "stock_uom": "Kg", "has_batch_no": 1},
		{"item_code": "Beef Sausage", "item_name": "Fresh Beef Sausage Links", "stock_uom": "Kg", "has_batch_no": 1},

		# 4. Offals & Direct Products
		{"item_code": "Ponmo", "item_name": "Ponmo (Cow Skin)", "stock_uom": "Kg", "has_batch_no": 1},
		{"item_code": "Cow Legs", "item_name": "Cow Legs (Cleaned)", "stock_uom": "Kg", "has_batch_no": 1},
		{"item_code": "Cow Liver", "item_name": "Fresh Cow Liver", "stock_uom": "Kg", "has_batch_no": 1},
		{"item_code": "Shaki (Tripe)", "item_name": "Shaki (Tripe Cleaned)", "stock_uom": "Kg", "has_batch_no": 1},
		{"item_code": "Oxtail", "item_name": "Whole Fresh Oxtail", "stock_uom": "Kg", "has_batch_no": 1},
		{"item_code": "Cow Head", "item_name": "Cow Head Meat", "stock_uom": "Kg", "has_batch_no": 1},
		{"item_code": "Cow Tongue", "item_name": "Fresh Cow Tongue", "stock_uom": "Kg", "has_batch_no": 1},
		{"item_code": "Cow Intestine", "item_name": "Cow Intestine (Roundabout)", "stock_uom": "Kg", "has_batch_no": 1},
		{"item_code": "Cow Heart", "item_name": "Fresh Cow Heart", "stock_uom": "Kg", "has_batch_no": 1},
		{"item_code": "Cow Lungs", "item_name": "Fresh Cow Lungs (Fuku)", "stock_uom": "Kg", "has_batch_no": 1},
		{"item_code": "Cow Kidney", "item_name": "Fresh Cow Kidney", "stock_uom": "Kg", "has_batch_no": 1},

		# 5. By-Products & Residuals
		{"item_code": "Beef Tendon", "item_name": "Beef Tendon", "stock_uom": "Kg", "has_batch_no": 1},
		{"item_code": "Beef Bone", "item_name": "Beef Soup & Broth Bones", "stock_uom": "Kg", "has_batch_no": 1},
		{"item_code": "Beef Trash", "item_name": "Beef Trimming Loss & Waste", "stock_uom": "Kg", "has_batch_no": 1},

		# 6. Packaging Consumables
		{"item_code": "Vacuum Pouch", "item_name": "Food Grade Vacuum Pouch", "stock_uom": "Nos", "has_batch_no": 0, "valuation_rate": 50.0},
		{"item_code": "Styrofoam Meat Tray Medium", "item_name": "Styrofoam Meat Tray (Medium)", "stock_uom": "Nos", "has_batch_no": 0, "valuation_rate": 60.0},
		{"item_code": "Styrofoam Meat Tray Large", "item_name": "Styrofoam Meat Tray (Large)", "stock_uom": "Nos", "has_batch_no": 0, "valuation_rate": 80.0},
		{"item_code": "Food Grade Cling Wrap", "item_name": "Food Grade Cling Wrap Per Unit", "stock_uom": "Nos", "has_batch_no": 0, "valuation_rate": 40.0},

		# 7. Retail Pre-Packs
		{"item_code": "Minced Beef 1kg Pack", "item_name": "Minced Beef 1kg Retail Pack", "stock_uom": "Pack", "has_batch_no": 1},
		{"item_code": "Shaki 1kg Pack", "item_name": "Shaki 1kg Pack (Retail)", "stock_uom": "Pack", "has_batch_no": 1},
		{"item_code": "Ribeye Steak 500g Pack", "item_name": "Ribeye Steak 500g Retail Pack", "stock_uom": "Pack", "has_batch_no": 1},
		{"item_code": "Beef Fillet 1kg Pack", "item_name": "Beef Fillet 1kg Retail Pack", "stock_uom": "Pack", "has_batch_no": 1},
		{"item_code": "Beef Sausage 500g Pack", "item_name": "Beef Sausage 500g Retail Pack", "stock_uom": "Pack", "has_batch_no": 1}
	]

	items = {}
	for it in items_data:
		code = it["item_code"]
		if not frappe.db.exists("Item", code):
			print(f"Creating Item: {code}")
			doc = frappe.get_doc({
				"doctype": "Item",
				"item_code": code,
				"item_name": it["item_name"],
				"item_group": "Meat & Butchery Products",
				"is_stock_item": 1,
				"stock_uom": it["stock_uom"],
				"has_batch_no": it.get("has_batch_no", 0),
				"valuation_rate": it.get("valuation_rate", 0.0)
			})
			doc.insert(ignore_permissions=True)
		items[code] = code

	return items


def ensure_breakdown_template(items):
	template_name = "Standard Nigerian Beef Cow Breakdown"
	if frappe.db.exists("Meat Breakdown Template", template_name):
		return frappe.get_doc("Meat Breakdown Template", template_name)

	cuts = [
		{"item_code": "Beef Fillet", "meat_cut_category": "Prime Cut", "expected_yield_pct": 2.0, "standard_selling_price": 15000.0},
		{"item_code": "Ribeye", "meat_cut_category": "Prime Cut", "expected_yield_pct": 2.5, "standard_selling_price": 14000.0},
		{"item_code": "Sirloin Beef", "meat_cut_category": "Prime Cut", "expected_yield_pct": 2.5, "standard_selling_price": 12000.0},
		{"item_code": "T-Bone", "meat_cut_category": "Prime Cut", "expected_yield_pct": 2.5, "standard_selling_price": 11000.0},
		{"item_code": "Tomahawk Beef", "meat_cut_category": "Prime Cut", "expected_yield_pct": 1.5, "standard_selling_price": 13500.0},
		{"item_code": "Minute Steak", "meat_cut_category": "Standard Cut", "expected_yield_pct": 2.0, "standard_selling_price": 10500.0},
		{"item_code": "Boneless Beef", "meat_cut_category": "Standard Cut", "expected_yield_pct": 16.0, "standard_selling_price": 9000.0},
		{"item_code": "Minced Beef", "meat_cut_category": "Standard Cut", "expected_yield_pct": 4.0, "standard_selling_price": 9500.0},
		{"item_code": "Beef Topside", "meat_cut_category": "Standard Cut", "expected_yield_pct": 4.0, "standard_selling_price": 9500.0},
		{"item_code": "Silver Side Beef", "meat_cut_category": "Standard Cut", "expected_yield_pct": 3.5, "standard_selling_price": 9200.0},
		{"item_code": "Beef Tonzo", "meat_cut_category": "Standard Cut", "expected_yield_pct": 2.5, "standard_selling_price": 8500.0},
		{"item_code": "Stewing Pack", "meat_cut_category": "Standard Cut", "expected_yield_pct": 5.0, "standard_selling_price": 7500.0},
		{"item_code": "Beef Shin", "meat_cut_category": "Standard Cut", "expected_yield_pct": 3.5, "standard_selling_price": 7000.0},
		{"item_code": "Shredded Beef", "meat_cut_category": "Standard Cut", "expected_yield_pct": 2.0, "standard_selling_price": 9000.0},
		{"item_code": "Beef Cube", "meat_cut_category": "Standard Cut", "expected_yield_pct": 3.0, "standard_selling_price": 9000.0},
		{"item_code": "Beef Sausage", "meat_cut_category": "Standard Cut", "expected_yield_pct": 2.5, "standard_selling_price": 8000.0},
		{"item_code": "Ponmo", "meat_cut_category": "Direct Product/Offal", "expected_yield_pct": 4.5, "standard_selling_price": 4500.0},
		{"item_code": "Cow Legs", "meat_cut_category": "Direct Product/Offal", "expected_yield_pct": 3.5, "standard_selling_price": 5000.0},
		{"item_code": "Cow Liver", "meat_cut_category": "Direct Product/Offal", "expected_yield_pct": 1.5, "standard_selling_price": 6500.0},
		{"item_code": "Shaki (Tripe)", "meat_cut_category": "Direct Product/Offal", "expected_yield_pct": 3.5, "standard_selling_price": 5500.0},
		{"item_code": "Oxtail", "meat_cut_category": "Direct Product/Offal", "expected_yield_pct": 1.0, "standard_selling_price": 8500.0},
		{"item_code": "Cow Head", "meat_cut_category": "Direct Product/Offal", "expected_yield_pct": 4.0, "standard_selling_price": 4500.0},
		{"item_code": "Cow Tongue", "meat_cut_category": "Direct Product/Offal", "expected_yield_pct": 0.8, "standard_selling_price": 6000.0},
		{"item_code": "Cow Intestine", "meat_cut_category": "Direct Product/Offal", "expected_yield_pct": 2.0, "standard_selling_price": 4000.0},
		{"item_code": "Cow Heart", "meat_cut_category": "Direct Product/Offal", "expected_yield_pct": 0.8, "standard_selling_price": 5000.0},
		{"item_code": "Cow Lungs", "meat_cut_category": "Direct Product/Offal", "expected_yield_pct": 1.2, "standard_selling_price": 3500.0},
		{"item_code": "Cow Kidney", "meat_cut_category": "Direct Product/Offal", "expected_yield_pct": 0.6, "standard_selling_price": 5500.0},
		{"item_code": "Beef Tendon", "meat_cut_category": "Bone/By-product", "expected_yield_pct": 1.5, "standard_selling_price": 3000.0},
		{"item_code": "Beef Bone", "meat_cut_category": "Bone/By-product", "expected_yield_pct": 19.5, "standard_selling_price": 800.0},
		{"item_code": "Beef Trash", "meat_cut_category": "Waste/Trim", "expected_yield_pct": 1.5, "standard_selling_price": 200.0}
	]

	template = frappe.get_doc({
		"doctype": "Meat Breakdown Template",
		"template_name": template_name,
		"animal_type": "Beef Cattle",
		"is_active": 1,
		"description": "Standard cut yield roster and benchmark NRV selling prices for Nigerian commercial beef cattle.",
		"items": cuts
	})
	template.insert(ignore_permissions=True)
	print(f"Created Meat Breakdown Template: {template_name}")
	return template


def ensure_initial_packaging_stock(company, warehouses):
	wh = warehouses["Deboning & Processing Floor"]
	items_to_stock = [
		("Vacuum Pouch", 2500, 50.0),
		("Styrofoam Meat Tray Medium", 1000, 60.0),
		("Styrofoam Meat Tray Large", 1000, 80.0),
		("Food Grade Cling Wrap", 500, 40.0)
	]

	# Check if stock exists
	existing_stock = frappe.db.get_value("Stock Ledger Entry", {"company": company.name, "item_code": "Vacuum Pouch", "warehouse": wh}, "name")
	if existing_stock:
		return

	print("Seeding initial stock for packaging consumables...")
	se = frappe.new_doc("Stock Entry")
	se.purpose = "Material Receipt"
	se.stock_entry_type = "Material Receipt"
	se.company = company.name
	se.posting_date = nowdate()
	se.posting_time = nowtime()
	for it, qty, rate in items_to_stock:
		se.append("items", {
			"t_warehouse": wh,
			"item_code": it,
			"qty": qty,
			"basic_rate": rate,
			"uom": "Nos",
			"conversion_factor": 1.0
		})
	se.remarks = "Initial seed inventory for Butchery packaging materials."
	se.insert(ignore_permissions=True)
	se.submit()


def generate_receiving_vouchers(company, warehouses, suppliers):
	vouchers = []
	receiving_dock = warehouses["Carcass Cold Room"]

	voucher_configs = [
		{
			"posting_date": add_days(nowdate(), -3),
			"supplier": "Oko-Oba Abattoir Agege",
			"supplier_invoice_no": "OKO-2026-9041",
			"dispatcher_name": "Babatunde Adeleke",
			"vehicle_no": "APP-914-LK",
			"receiving_outlet": receiving_dock,
			"carcass_item": "Whole Beef Carcass",
			"number_of_carcasses": 2,
			"batch_no": "NG-COW-2026-001",
			"invoiced_weight": 780.0,
			"invoiced_rate_per_kg": 3800.0,
			"received_weight": 772.5,
			"shortage_treatment": "Absorb in Valuation (Capitalize Loss)"
		},
		{
			"posting_date": add_days(nowdate(), -2),
			"supplier": "Kara Cattle Market Ogun-Lagos",
			"supplier_invoice_no": "KARA-INV-4410",
			"dispatcher_name": "Musa Danladi",
			"vehicle_no": "ABJ-315-TR",
			"receiving_outlet": receiving_dock,
			"carcass_item": "Whole Beef Carcass",
			"number_of_carcasses": 2,
			"batch_no": "NG-COW-2026-002",
			"invoiced_weight": 850.0,
			"invoiced_rate_per_kg": 3750.0,
			"received_weight": 831.0,
			"shortage_treatment": "Book as Transit Shrinkage Expense"
		},
		{
			"posting_date": add_days(nowdate(), -1),
			"supplier": "Ikorodu Livestock Hub",
			"supplier_invoice_no": "IKR-0829",
			"dispatcher_name": "Emeka Okafor",
			"vehicle_no": "KJA-482-XY",
			"receiving_outlet": receiving_dock,
			"carcass_item": "Goat Carcass",
			"number_of_carcasses": 5,
			"batch_no": "NG-GOAT-2026-001",
			"invoiced_weight": 115.0,
			"invoiced_rate_per_kg": 4500.0,
			"received_weight": 113.2,
			"shortage_treatment": "Absorb in Valuation (Capitalize Loss)"
		}
	]

	for cfg in voucher_configs:
		doc = frappe.new_doc("Butchery Receiving Voucher")
		doc.company = company.name
		doc.posting_date = cfg["posting_date"]
		doc.supplier = cfg["supplier"]
		doc.supplier_invoice_no = cfg["supplier_invoice_no"]
		doc.dispatcher_name = cfg["dispatcher_name"]
		doc.vehicle_no = cfg["vehicle_no"]
		doc.receiving_outlet = cfg["receiving_outlet"]
		doc.carcass_item = cfg["carcass_item"]
		doc.number_of_carcasses = cfg["number_of_carcasses"]
		doc.batch_no = cfg["batch_no"]
		doc.invoiced_weight = cfg["invoiced_weight"]
		doc.invoiced_rate_per_kg = cfg["invoiced_rate_per_kg"]
		doc.received_weight = cfg["received_weight"]
		doc.shortage_treatment = cfg["shortage_treatment"]
		doc.insert(ignore_permissions=True)
		doc.submit()
		print(f"Created & Submitted Receiving Voucher: {doc.name} (Batch: {cfg['batch_no']})")
		vouchers.append(doc)

	return vouchers


def generate_meat_breakdown(company, warehouses, receiving_vouchers, template):
	breakdowns = []
	src_wh = warehouses["Carcass Cold Room"]
	tgt_wh = warehouses["Deboning & Processing Floor"]

	# Process voucher 1: NG-COW-2026-001
	rec1 = receiving_vouchers[0]
	mb1 = frappe.new_doc("Meat Breakdown")
	mb1.company = company.name
	mb1.posting_date = add_days(rec1.posting_date, 1)
	mb1.template = template.name
	mb1.source_warehouse = src_wh
	mb1.target_warehouse = tgt_wh
	mb1.carcass_item = rec1.carcass_item
	mb1.source_batch_no = rec1.batch_no
	mb1.source_carcass_weight = rec1.received_weight
	mb1.carcass_valuation_rate = rec1.effective_valuation_rate

	# Populate cuts with realistic floor scale readings
	# Total in: 772.5kg. Expected yields scale ~ 748.8kg outturn (23.7kg cutting loss / 3.07%)
	scale_multiplier = rec1.received_weight / 100.0  # ~7.725
	actual_yield_factors = {
		"Beef Fillet": 1.95,
		"Ribeye": 2.45,
		"Sirloin Beef": 2.48,
		"T-Bone": 2.45,
		"Tomahawk Beef": 1.48,
		"Minute Steak": 1.95,
		"Boneless Beef": 15.80,
		"Minced Beef": 3.90,
		"Beef Topside": 3.95,
		"Silver Side Beef": 3.45,
		"Beef Tonzo": 2.45,
		"Stewing Pack": 4.90,
		"Beef Shin": 3.40,
		"Shredded Beef": 1.95,
		"Beef Cube": 2.95,
		"Beef Sausage": 2.45,
		"Ponmo": 4.40,
		"Cow Legs": 3.45,
		"Cow Liver": 1.45,
		"Shaki (Tripe)": 3.40,
		"Oxtail": 0.98,
		"Cow Head": 3.90,
		"Cow Tongue": 0.78,
		"Cow Intestine": 1.95,
		"Cow Heart": 0.78,
		"Cow Lungs": 1.15,
		"Cow Kidney": 0.58,
		"Beef Tendon": 1.45,
		"Beef Bone": 19.10,
		"Beef Trash": 1.40
	}

	for item in template.items:
		factor = actual_yield_factors.get(item.item_code, item.expected_yield_pct * 0.98)
		act_wt = round(factor * scale_multiplier, 2)
		mb1.append("cuts", {
			"item_code": item.item_code,
			"meat_cut_category": item.meat_cut_category,
			"expected_yield_pct": item.expected_yield_pct,
			"standard_selling_price": item.standard_selling_price,
			"actual_weight": act_wt
		})

	mb1.insert(ignore_permissions=True)
	mb1.submit()
	print(f"Created & Submitted Meat Breakdown: {mb1.name} (Source: {rec1.batch_no}, Outturn: {mb1.total_outturn_weight}kg)")
	breakdowns.append(mb1)

	# Process voucher 2: NG-COW-2026-002
	rec2 = receiving_vouchers[1]
	mb2 = frappe.new_doc("Meat Breakdown")
	mb2.company = company.name
	mb2.posting_date = nowdate()
	mb2.template = template.name
	mb2.source_warehouse = src_wh
	mb2.target_warehouse = tgt_wh
	mb2.carcass_item = rec2.carcass_item
	mb2.source_batch_no = rec2.batch_no
	mb2.source_carcass_weight = rec2.received_weight
	mb2.carcass_valuation_rate = rec2.effective_valuation_rate

	scale_multiplier2 = rec2.received_weight / 100.0
	for item in template.items:
		factor = actual_yield_factors.get(item.item_code, item.expected_yield_pct * 0.98)
		act_wt = round(factor * scale_multiplier2, 2)
		mb2.append("cuts", {
			"item_code": item.item_code,
			"meat_cut_category": item.meat_cut_category,
			"expected_yield_pct": item.expected_yield_pct,
			"standard_selling_price": item.standard_selling_price,
			"actual_weight": act_wt
		})

	mb2.insert(ignore_permissions=True)
	mb2.submit()
	print(f"Created & Submitted Meat Breakdown: {mb2.name} (Source: {rec2.batch_no}, Outturn: {mb2.total_outturn_weight}kg)")
	breakdowns.append(mb2)

	return breakdowns


def generate_meat_conversions(company, warehouses, breakdowns):
	conversions = []
	proc_wh = warehouses["Deboning & Processing Floor"]
	mb = breakdowns[0]

	# Find Boneless Beef child cut row from breakdown
	boneless_row = next((c for c in mb.cuts if c.item_code == "Boneless Beef"), None)
	if not boneless_row:
		return conversions

	conv = frappe.new_doc("Meat Conversion")
	conv.company = company.name
	conv.posting_date = nowdate()
	conv.warehouse = proc_wh
	conv.source_item = "Boneless Beef"
	conv.source_batch_no = boneless_row.batch_no
	conv.convert_qty = 40.0
	conv.source_valuation_rate = boneless_row.cost_per_kg or 7500.0
	conv.target_item = "Minced Beef"
	conv.target_qty = 39.2  # 0.8kg grinder residue loss (2.0%)
	conv.loss_treatment = "Absorb into Target Product Cost"

	conv.insert(ignore_permissions=True)
	conv.submit()
	print(f"Created & Submitted Meat Conversion: {conv.name} (40kg Boneless -> 39.2kg Minced, Batch: {conv.target_batch_no})")
	conversions.append(conv)
	return conversions


def generate_portioning_entries(company, warehouses, breakdowns, conversions):
	entries = []
	wh = warehouses["Deboning & Processing Floor"]
	mb = breakdowns[0]

	# Entry 1: Portions converted Minced Beef into 1kg retail packs
	minced_batch = conversions[0].target_batch_no if conversions else None
	pe1 = frappe.new_doc("Meat Portioning Entry")
	pe1.company = company.name
	pe1.posting_date = nowdate()
	pe1.warehouse = wh
	pe1.bulk_item = "Minced Beef"
	pe1.bulk_batch_no = minced_batch
	pe1.bulk_weight_used = 25.0
	pe1.bulk_valuation_rate = conversions[0].target_valuation_rate if conversions else 8000.0
	pe1.retail_item = "Minced Beef 1kg Pack"
	pe1.pack_size_kg = 1.0
	pe1.packs_produced = 25
	pe1.shelf_life_days = 21

	pe1.append("packaging_materials", {"item_code": "Vacuum Pouch", "qty": 25, "uom": "Nos"})
	pe1.append("packaging_materials", {"item_code": "Styrofoam Meat Tray Medium", "qty": 25, "uom": "Nos"})

	pe1.insert(ignore_permissions=True)
	pe1.submit()
	print(f"Created & Submitted Portioning Entry: {pe1.name} (25kg Minced -> 25 packs, Expiry: {pe1.expiry_date})")
	entries.append(pe1)

	# Entry 2: Portions bulk Shaki into 1kg retail packs
	shaki_row = next((c for c in mb.cuts if c.item_code == "Shaki (Tripe)"), None)
	if shaki_row:
		pe2 = frappe.new_doc("Meat Portioning Entry")
		pe2.company = company.name
		pe2.posting_date = nowdate()
		pe2.warehouse = wh
		pe2.bulk_item = "Shaki (Tripe)"
		pe2.bulk_batch_no = shaki_row.batch_no
		pe2.bulk_weight_used = 15.0
		pe2.bulk_valuation_rate = shaki_row.cost_per_kg or 4500.0
		pe2.retail_item = "Shaki 1kg Pack"
		pe2.pack_size_kg = 1.0
		pe2.packs_produced = 15
		pe2.shelf_life_days = 14

		pe2.append("packaging_materials", {"item_code": "Vacuum Pouch", "qty": 15, "uom": "Nos"})

		pe2.insert(ignore_permissions=True)
		pe2.submit()
		print(f"Created & Submitted Portioning Entry: {pe2.name} (15kg Shaki -> 15 packs, Expiry: {pe2.expiry_date})")
		entries.append(pe2)

	return entries


def generate_return_vouchers(company, warehouses, customers):
	returns = []
	ret_wh = warehouses["Customer Returns Holding"]

	# Customer returns 15kg Minced Beef due to hospitality dispatch excess
	brv = frappe.new_doc("Butchery Return Voucher")
	brv.company = company.name
	brv.posting_date = nowdate()
	brv.customer = "Eko Hotel & Suites Victoria Island"
	brv.driver_rider = "Emeka Okafor"
	brv.vehicle_no = "KJA-482-XY"
	brv.return_warehouse = ret_wh
	brv.item_code = "Minced Beef"
	brv.item_valuation_rate = 9500.0
	brv.dispatched_weight = 50.0
	brv.customer_rejected_weight = 15.0
	brv.actual_store_received_weight = 14.1  # 0.9kg return transit loss (6.0%)

	brv.insert(ignore_permissions=True)
	brv.submit()
	print(f"Created & Submitted Butchery Return Voucher: {brv.name} (Rejected: 15kg, Received: 14.1kg, Shortage: {brv.return_transit_loss}kg)")
	returns.append(brv)

	return returns
