// Copyright (c) 2026, Tumel and contributors
// For license information, please see license.txt

frappe.ui.form.on('Meat Conversion', {
	setup: function(frm) {
		frm.set_query('warehouse', function() {
			return { filters: { company: frm.doc.company || 'Tumel', is_group: 0 } };
		});
		frm.set_query('source_item', function() {
			return { filters: { is_stock_item: 1 } };
		});
		frm.set_query('target_item', function() {
			return { filters: { is_stock_item: 1 } };
		});
	},

	source_item: function(frm) {
		fetch_source_stock(frm);
	},

	source_batch_no: function(frm) {
		fetch_source_stock(frm);
	},

	warehouse: function(frm) {
		fetch_source_stock(frm);
	},

	convert_qty: function(frm) {
		recalc_conversion(frm);
	},

	target_qty: function(frm) {
		recalc_conversion(frm);
	},

	source_valuation_rate: function(frm) {
		recalc_conversion(frm);
	},

	loss_treatment: function(frm) {
		recalc_conversion(frm);
	}
});

function fetch_source_stock(frm) {
	if (frm.doc.source_item && frm.doc.warehouse) {
		frappe.call({
			method: 'erpnext.stock.utils.get_latest_stock_qty',
			args: {
				item_code: frm.doc.source_item,
				warehouse: frm.doc.warehouse
			},
			callback: function(r) {
				if (r.message !== undefined) {
					frm.set_value('available_qty', r.message);
				}
			}
		});

		frappe.call({
			method: 'erpnext.stock.utils.get_incoming_rate',
			args: {
				item_code: frm.doc.source_item,
				warehouse: frm.doc.warehouse,
				posting_date: frm.doc.posting_date,
				posting_time: frm.doc.posting_time,
				qty: flt(frm.doc.convert_qty) || 1,
				batch_no: frm.doc.source_batch_no
			},
			callback: function(r) {
				if (r.message) {
					frm.set_value('source_valuation_rate', r.message);
					recalc_conversion(frm);
				}
			}
		});
	}
}

function recalc_conversion(frm) {
	let c_qty = flt(frm.doc.convert_qty);
	let s_rate = flt(frm.doc.source_valuation_rate);
	let t_qty = flt(frm.doc.target_qty);

	let s_cost = roundDec(c_qty * s_rate, 2);
	frm.set_value('source_total_cost', s_cost);

	if (c_qty > 0 && t_qty > 0) {
		let loss = roundDec(c_qty - t_qty, 3);
		let loss_pct = roundDec((loss / c_qty) * 100.0, 2);
		frm.set_value('conversion_loss', loss);
		frm.set_value('conversion_loss_pct', loss_pct);

		if (frm.doc.loss_treatment === 'Absorb into Target Product Cost') {
			let t_rate = roundDec(s_cost / t_qty, 2);
			frm.set_value('target_valuation_rate', t_rate);
		} else {
			frm.set_value('target_valuation_rate', s_rate);
		}
	}
}

function roundDec(num, scale) {
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
