# Dashboard 2 — Purchase & Sales Territory Mapping Specification

- **Target MongoDB Collection**: `territory_transactions`
- **ERP Source Instance**: `http://erp.fpohub.com`
- **ERP DocType / Dataset**: `Purchase Invoice`
- **Source Type**: `doctype`
- **Sync Strategy**: `timestamp` (incremental watermarking)
- **Mapper Class**: `TerritoryTransactionsMapper`

## Field Mapping Matrix

| Dashboard Field | Target Type | ERP Source Field | Transformation / Derivation | Status |
| :--- | :--- | :--- | :--- | :--- |
| `territory` | string | `territory` / `place_of_supply` / `billing_address_display` / `company` | Resolved region name (e.g., `"Telangana"`, `"Warangal"`) | **Verified** |
| `date` | string (`DD-MM-YYYY`) | `posting_date` / `bill_date` | Converted via `normalize_date()` into `DD-MM-YYYY` | **Verified** |
| `purchase_amount` | float | `grand_total` / `net_total` | Summed procurement amount | **Verified** |
| `sales_amount` | float (nullable) | *None* | Set to `null` (Purchase Invoice represents procurement only) | **Unavailable (Null)** |

## Aggregation Rules
- **Group By**: `["territory", "date"]`
- **Sum**: `purchase_amount`
