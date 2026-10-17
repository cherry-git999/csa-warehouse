# Dashboard 6 — Revenue Analysis Mapping Specification

- **Target MongoDB Collection**: `revenue_analysis`
- **ERP Source Instance**: `http://erp.fpohub.com`
- **ERP DocType / Dataset**: `Purchase Invoice`
- **Source Type**: `doctype`
- **Sync Strategy**: `timestamp` (incremental watermarking)
- **Mapper Class**: `RevenueAnalysisMapper`

## Field Mapping Matrix

| Dashboard Field | Target Type | ERP Source Field | Transformation / Derivation | Status |
| :--- | :--- | :--- | :--- | :--- |
| `territory` | string | `territory` / `place_of_supply` / `shipping_address_display` / `company` | Resolved regional market territory | **Verified** |
| `month` | string | `posting_date` / `bill_date` | Abbreviated month string (e.g. `"Jun"`, `"Dec"`) | **Verified** |
| `purchase_amount` | float | `grand_total` / `net_total` | Summed monthly procurement value | **Verified** |
| `sales_amount` | float (nullable) | *None* | Set to `null` (Purchase Invoice represents procurement only) | **Unavailable (Null)** |

## Aggregation Rules
- **Group By**: `["territory", "month"]`
- **Sum**: `purchase_amount`
