// Copyright (c) 2026, Tumel and contributors
// For license information, please see license.txt

frappe.ui.form.on('Butchery Return Voucher', {
	setup: function(frm) {
		frm.set_query('return_warehouse', function() {
			return { filters: { company: frm.doc.company || 'Tumel', is_group: 0 } };
		});
	},

	item_code: function(frm) {
		if (frm.doc.item_code) {
			frappe.db.get_value('Item', frm.doc.item_code, 'valuation_rate', function(r) {
				if (r && r.valuation_rate) {
					frm.set_value('item_valuation_rate', r.valuation_rate);
					calc_return_variance(frm);
				}
			});
		}
	},

	customer_rejected_weight: function(frm) {
		calc_return_variance(frm);
	},

	actual_store_received_weight: function(frm) {
		calc_return_variance(frm);
	},

	item_valuation_rate: function(frm) {
		calc_return_variance(frm);
	}
});

function calc_return_variance(frm) {
	let rej_wt = flt(frm.doc.customer_rejected_weight);
	let rec_wt = flt(frm.doc.actual_store_received_weight);
	let rate = flt(frm.doc.item_valuation_rate);

	if (rej_wt > 0 && rec_wt > 0) {
		let loss = roundDec(rej_wt - rec_wt, 3);
		let loss_pct = roundDec((loss / rej_wt) * 100.0, 2);
		let loss_amt = roundDec(loss * rate, 2);

		frm.set_value('return_transit_loss', loss);
		frm.set_value('loss_pct', loss_pct);
		frm.set_value('loss_amount', loss_amt);
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
