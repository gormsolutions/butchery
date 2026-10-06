// Copyright (c) 2026, Tumel and contributors
// For license information, please see license.txt

frappe.ui.form.on('Meat Breakdown', {
	setup: function(frm) {
		frm.set_query('source_warehouse', function() {
			return { filters: { company: frm.doc.company || 'Tumel', is_group: 0 } };
		});
		frm.set_query('target_warehouse', function() {
			return { filters: { company: frm.doc.company || 'Tumel', is_group: 0 } };
		});
	},

	refresh: function(frm) {
		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(__('Load Template Cuts'), function() {
				load_template(frm);
			}, __('Actions'));

			frm.add_custom_button(__('Recalculate Yield & NRV'), function() {
				calculate_nrv(frm);
			}, __('Actions'));
		}
	},

	template: function(frm) {
		if (frm.doc.template && (!frm.doc.cuts || frm.doc.cuts.length === 0)) {
			load_template(frm);
		}
	},

	source_carcass_weight: function(frm) {
		calculate_nrv(frm);
	},

	carcass_valuation_rate: function(frm) {
		calculate_nrv(frm);
	}
});

frappe.ui.form.on('Meat Breakdown Output', {
	actual_weight: function(frm, cdt, cdn) {
		calculate_nrv(frm);
	},

	standard_selling_price: function(frm, cdt, cdn) {
		calculate_nrv(frm);
	}
});

function load_template(frm) {
	if (!frm.doc.template) {
		frappe.msgprint(__('Please select a Breakdown Cut Template first.'));
		return;
	}

	frappe.call({
		method: 'butchery_management.butchery_management.doctype.meat_breakdown.meat_breakdown.get_template_cuts',
		args: { template_name: frm.doc.template },
		freeze: true,
		freeze_message: __('Loading cut template...'),
		callback: function(r) {
			if (r.message && r.message.length) {
				frm.clear_table('cuts');
				r.message.forEach(cut => {
					let row = frm.add_child('cuts');
					row.item_code = cut.item_code;
					row.item_name = cut.item_name;
					row.meat_cut_category = cut.meat_cut_category;
					row.expected_yield_pct = cut.expected_yield_pct;
					row.standard_selling_price = cut.standard_selling_price;
					row.actual_weight = 0.0;
				});
				frm.refresh_field('cuts');
				frappe.show_alert({
					message: __('Loaded {0} cuts from template.', [r.message.length]),
					indicator: 'green'
				});
				calculate_nrv(frm);
			}
		}
	});
}

function calculate_nrv(frm) {
	let in_wt = flt(frm.doc.source_carcass_weight);
	let in_rate = flt(frm.doc.carcass_valuation_rate);
	let total_cost = roundVal(in_wt * in_rate, 2);
	frm.set_value('total_carcass_cost', total_cost);

	let cuts = frm.doc.cuts || [];
	let total_outturn = 0.0;
	let total_sales = 0.0;

	cuts.forEach(row => {
		let wt = flt(row.actual_weight);
		let sp = flt(row.standard_selling_price);
		let s_val = roundVal(wt * sp, 2);
		row.sales_value = s_val;
		row.actual_yield_pct = in_wt > 0 ? roundVal((wt / in_wt) * 100.0, 2) : 0.0;
		total_outturn += wt;
		total_sales += s_val;
	});

	let loss_wt = roundVal(in_wt - total_outturn, 3);
	let loss_pct = in_wt > 0 ? roundVal((loss_wt / in_wt) * 100.0, 2) : 0.0;
	let net_yield = in_wt > 0 ? roundVal((total_outturn / in_wt) * 100.0, 2) : 0.0;

	frm.set_value('total_outturn_weight', roundVal(total_outturn, 3));
	frm.set_value('cutting_loss_weight', loss_wt);
	frm.set_value('cutting_loss_pct', loss_pct);
	frm.set_value('net_yield_pct', net_yield);
	frm.set_value('total_sales_value', roundVal(total_sales, 2));

	// Allocate costs via NRV
	cuts.forEach(row => {
		let wt = flt(row.actual_weight);
		if (total_sales > 0 && wt > 0) {
			row.sales_value_ratio = roundVal((row.sales_value / total_sales) * 100.0, 2);
			row.allocated_cost = roundVal(total_cost * (row.sales_value / total_sales), 2);
			row.cost_per_kg = roundVal(row.allocated_cost / wt, 2);
		} else {
			row.sales_value_ratio = 0.0;
			row.allocated_cost = 0.0;
			row.cost_per_kg = 0.0;
		}
	});

	frm.refresh_field('cuts');
}

function roundVal(num, scale) {
	if(!("" + num).includes("e")) {
		return +(Math.round(num + "e+" + scale)  + "e-" + scale);
	} else {
		let arr = ("" + num).split("e");
		let sig = ""
		if(+arr[1] + scale > 0) {
			sig = "+";
		}
		return +(Math.round(+arr[0] + "e" + sig + (+arr[1] + scale)) + "e-" + scale);
	}
}
