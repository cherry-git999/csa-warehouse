# Dashboard 4 — Stock Movement Mapping Specification

- **Target MongoDB Collection**: `stock_movement`
- **ERP Source Instance**: `http://erp.fpohub.com`
- **ERP DocType / Dataset**: `Stock Balance`
- **Source Type**: `query_report`
- **Sync Strategy**: `snapshot` (fresh report execution replacement)
- **Mapper Class**: `StockMovementMapper`

## Field Mapping Matrix

| Dashboard Field | Target Type | ERP Source Field | Transformation / Derivation | Status |
| :--- | :--- | :--- | :--- | :--- |
| `date` | string (`DD-MM-YYYY`) | `posting_date` / `to_date` / runtime date | Report reference date formatted as `DD-MM-YYYY` | **Verified** |
| `in_qty` | float | `in_qty` | Total inflow quantity across items in report | **Verified** |
| `out_qty` | float | `out_qty` | Total outflow quantity across items in report | **Verified** |
| `balance_value` | float | `bal_val` / `stock_value` | Ending stock valuation across items | **Verified** |

## Aggregation Rules
- **Group By**: `["date"]`
- **Sum**: `in_qty`, `out_qty`, `balance_value`
