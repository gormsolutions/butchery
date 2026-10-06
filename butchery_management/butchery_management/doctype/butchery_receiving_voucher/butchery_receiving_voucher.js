// Copyright (c) 2026, Tumel and contributors
// For license information, please see license.txt

frappe.ui.form.on('Butchery Receiving Voucher', {
	setup: function(frm) {
		frm.set_query('receiving_outlet', function() {
			return {
				filters: {
					company: frm.doc.company || 'Tumel',
					is_group: 0
				}
			};
		});
		frm.set_query('carcass_item', function() {
			return {
				filters: {
					is_stock_item: 1
				}
			};
		});
	},

	invoiced_weight: function(frm) {
		calculate_weights(frm);
	},

	invoiced_rate_per_kg: function(frm) {
		calculate_weights(frm);
	},

	received_weight: function(frm) {
		calculate_weights(frm);
	},

	shortage_treatment: function(frm) {
		calculate_weights(frm);
	}
});

function calculate_weights(frm) {
	let inv_wt = flt(frm.doc.invoiced_weight);
	let inv_rate = flt(frm.doc.invoiced_rate_per_kg);
	let rec_wt = flt(frm.doc.received_weight);

	let inv_amt = roundNumber(inv_wt * inv_rate, 2);
	frm.set_value('invoiced_amount', inv_amt);

	if (inv_wt > 0 && rec_wt > 0) {
		let variance = roundNumber(inv_wt - rec_wt, 3);
		let var_pct = roundNumber((variance / inv_wt) * 100.0, 2);
		let var_amt = roundNumber(variance * inv_rate, 2);

		frm.set_value('weight_variance', variance);
		frm.set_value('variance_pct', var_pct);
		frm.set_value('variance_amount', var_amt);

		if (frm.doc.shortage_treatment === 'Absorb in Valuation (Capitalize Loss)') {
			let eff_rate = roundNumber(inv_amt / rec_wt, 2);
			frm.set_value('effective_valuation_rate', eff_rate);
		} else {
			frm.set_value('effective_valuation_rate', inv_rate);
		}
	}
}

function roundNumber(num, scale) {
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
