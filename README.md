# Butchery Management for ERPNext

A comprehensive meat processing, livestock receiving reconciliation, carcass disassembly (inverse manufacturing), and retail portioning app for ERPNext.

---

## Key Features

1. **Inbound Receiving Reconciliation (`Butchery Receiving Voucher`)**:
   - Reconciles live slaughterhouse invoiced weight vs actual receiving dock scale weight.
   - Computes transit shrinkage / fluid loss.
   - Provides 3 automated financial loss treatments: Absorb in Valuation (Capitalize Loss), Book as Expense, or Deduct from Supplier.
   - Generates native ERPNext `Material Receipt` Stock Entries.

2. **Carcass Breakdown / Deboning (`Meat Breakdown`)**:
   - One-to-many inverse manufacturing from 1 parent carcass to 30+ sellable cuts.
   - Automated Net Realizable Value (NRV) cost allocation engine ensuring total allocated costs equal carcass cost.
   - Mass balance conservation checks preventing phantom inventory.
   - Collision-free child batch generation (`{prefix}-{parent_batch}`).
   - Generates native ERPNext `Repack` Stock Entries.

3. **Internal Product Conversions (`Meat Conversion`)**:
   - Transforms one cut into another (e.g. Boneless Beef $\rightarrow$ Minced Beef).
   - Tracks grinder and trimming shrinkage.
   - Automatically re-allocates valuation rate across converted yields.

4. **Portioning, Packaging & Retail Expiry (`Meat Portioning Entry`)**:
   - Converts bulk meat (kg) into consumer retail packs (units).
   - Consumes packaging materials (pouches, trays, pads).
   - Dynamic unit pack cost rollups.
   - Auto-calculates shelf-life expiry dates and generates retail POS barcodes.

5. **B2B Dispatch & Returns Handling (`Butchery Return Voucher`)**:
   - Tracks customer rejected weight vs store dock received weight.
   - Audits in-transit vehicle/driver return shrinkage.
   - Restocks under dedicated return batches via native `Material Receipt`.

6. **Dedicated Butchery Reporting**:
   - Inbound Weight Variance Report
   - Carcass Breakdown and Yield Report
   - Customer Return and Transit Variance Report

---

## Comprehensive User Guide

For detailed operational instructions, mathematical formulas, and step-by-step guides, see:
* **[Comprehensive User Guide](docs/USER_GUIDE.md)**

---

## Installation

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app https://github.com/stevesaul/butchery_management.git
bench --site <site-name> install-app butchery_management
bench --site <site-name> migrate
```

---

## License

MIT
