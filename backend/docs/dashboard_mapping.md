# Dashboard-Specific ERP Data Mapping Specification

This document defines the schema transformation, field mapping, aggregation rules, and availability status for each of the six CSA Warehouse dashboards connecting to ERPNext instances.

---

## 1. Dashboard 1 — NF Coordinator Performance

- **Target MongoDB Collection**: `nf_coordinator_activities`
- **ERP Source Instance**: `http://erp.csa-india.org`
- **ERP DocType / Dataset**: `CC Daily Reports`
- **Source Type**: `doctype`
- **Sync Strategy**: `timestamp` (incremental watermarking)
- **Mapper Class**: `NFCoordinatorMapper`

### Field Mapping Matrix

| Dashboard Field | Target Type | ERP Source Field | Transformation / Derivation | Status |
| :--- | :--- | :--- | :--- | :--- |
| `coordinator_name` | string | `parent.name_of_nf_coordinator` | Extracted from parent document or row owner | **Verified** |
| `district` | string | `child.mandal` / `child.village` / `child.name_of_the_fpo` / `parent.district` | Extracted from activity location fields; fallback to `"General"` | **Verified** |
| `date` | string (`DD-MM-YYYY`) | `child.date` / `parent.creation` | Converted via `normalize_date()` into `DD-MM-YYYY` | **Verified** |
| `type_of_activity` | string | `child.activity` / `child.sub_activity` | Extracted from child tables `field_visit` and `cc_daily_reports` | **Verified** |
| `planned_activities`| integer | Activity event instance | Aggregated event count per coordinator/date/type | **Verified** |
| `actual_activities` | integer | Activity event instance | Aggregated event count per coordinator/date/type | **Verified** |
| `total_score` | integer | Derived (`actual_activities * 10`) | Evaluated activity score | **Derived** |

### Aggregation Rules
- **Group By**: `["coordinator_name", "district", "date", "type_of_activity"]`
- **Sum**: `planned_activities`, `actual_activities`, `total_score`

---

## 2. Dashboard 2 — Purchase & Sales Territory

- **Target MongoDB Collection**: `territory_transactions`
- **ERP Source Instance**: `http://erp.fpohub.com`
- **ERP DocType / Dataset**: `Purchase Invoice`
- **Source Type**: `doctype`
- **Sync Strategy**: `timestamp` (incremental watermarking)
- **Mapper Class**: `TerritoryTransactionsMapper`

### Field Mapping Matrix

| Dashboard Field | Target Type | ERP Source Field | Transformation / Derivation | Status |
| :--- | :--- | :--- | :--- | :--- |
| `territory` | string | `territory` / `place_of_supply` / `billing_address_display` / `company` | Resolved region name (e.g., `"Telangana"`, `"Warangal"`) | **Verified** |
| `date` | string (`DD-MM-YYYY`) | `posting_date` / `bill_date` | Converted via `normalize_date()` into `DD-MM-YYYY` | **Verified** |
| `purchase_amount` | float | `grand_total` / `net_total` | Summed procurement amount | **Verified** |
| `sales_amount` | float (nullable) | *None* | Set to `null` (Purchase Invoice represents procurement only) | **Unavailable (Null)** |

### Aggregation Rules
- **Group By**: `["territory", "date"]`
- **Sum**: `purchase_amount`

---

## 3. Dashboard 3 — Farmer Income & Visits

- **Target MongoDB Collection**: `farmer_income_visits`
- **ERP Source Instance**: `http://erp.csa-india.org`
- **ERP DocType / Dataset**: `CC Daily Reports` (specifically extracting `consolidated_report` child table)
- **Source Type**: `doctype`
- **Sync Strategy**: `timestamp` (incremental watermarking)
- **Mapper Class**: `FarmerIncomeVisitsMapper`

### Field Mapping Matrix

| Dashboard Field | Target Type | ERP Source Field | Transformation / Derivation | Status |
| :--- | :--- | :--- | :--- | :--- |
| `coordinator_name` | string | `parent.name_of_nf_coordinator` | Extracted from parent document coordinator link | **Verified** |
| `month` | string | `parent.month` | Extracted from parent document month (e.g. `"August"`) | **Verified** |
| `village` | string | `child.village` / `child.name_of_the_fpo` / `parent.village` | Village or FPO cluster name | **Verified** |
| `farmers_met` | integer | `child.number_of_participants` | Participant count parsed from `consolidated_report` | **Verified** |
| `visits` | integer | `child.sub_activity_count` | Activity frequency count parsed from `consolidated_report` | **Verified** |
| `score` | integer | Derived (`visits * 10`) | Computed performance score | **Derived** |
| `income` | float (nullable) | *None* | Awaiting separate farmer ledger integration; preserved as `null` | **Unavailable (Null)** |
| `net_income` | float (nullable) | *None* | Awaiting separate farmer ledger integration; preserved as `null` | **Unavailable (Null)** |
| `yield` | float (nullable) | *None* | Awaiting separate harvest yield integration; preserved as `null` | **Unavailable (Null)** |

### Aggregation Rules
- **Group By**: `["coordinator_name", "month", "village"]`
- **Sum**: `farmers_met`, `visits`, `score`

---

## 4. Dashboard 4 — Stock Movement

- **Target MongoDB Collection**: `stock_movement`
- **ERP Source Instance**: `http://erp.fpohub.com`
- **ERP DocType / Dataset**: `Stock Balance`
- **Source Type**: `query_report`
- **Sync Strategy**: `snapshot` (fresh report execution replacement)
- **Mapper Class**: `StockMovementMapper`

### Field Mapping Matrix

| Dashboard Field | Target Type | ERP Source Field | Transformation / Derivation | Status |
| :--- | :--- | :--- | :--- | :--- |
| `date` | string (`DD-MM-YYYY`) | `posting_date` / `to_date` / runtime date | Report reference date formatted as `DD-MM-YYYY` | **Verified** |
| `in_qty` | float | `in_qty` | Total inflow quantity across items in report | **Verified** |
| `out_qty` | float | `out_qty` | Total outflow quantity across items in report | **Verified** |
| `balance_value` | float | `bal_val` / `stock_value` | Ending stock valuation across items | **Verified** |

### Aggregation Rules
- **Group By**: `["date"]`
- **Sum**: `in_qty`, `out_qty`, `balance_value`

---

## 5. Dashboard 5 — Stock Inventory

- **Target MongoDB Collection**: `stock_inventory`
- **ERP Source Instance**: `http://erp.fpohub.com`
- **ERP DocType / Dataset**: `Stock Balance`
- **Source Type**: `query_report`
- **Sync Strategy**: `snapshot` (fresh report execution replacement)
- **Mapper Class**: `StockInventoryMapper`

### Field Mapping Matrix

| Dashboard Field | Target Type | ERP Source Field | Transformation / Derivation | Status |
| :--- | :--- | :--- | :--- | :--- |
| `company` | string | `company` | Company name (e.g. `"Nelathalli Farmer Producer Company Limited"`) | **Verified** |
| `warehouse` | string | `warehouse` | Warehouse name (e.g. `"Vana parthy 1 - NFPCL"`) | **Verified** |
| `item_name` | string | `item_name` / `item_code` | Item title or item identifier | **Verified** |
| `item_group` | string | `item_group` | Item category (e.g. `"Farm Machinery"`, `"Produce"`) | **Verified** |
| `stock_qty` | float | `bal_qty` | Current balance quantity | **Verified** |
| `stock_value` | float | `bal_val` | Current balance valuation in INR | **Verified** |

### Aggregation Rules
- **Granularity**: Item and Warehouse level
- **Group By**: `["company", "warehouse", "item_name", "item_group"]`
- **Sum**: `stock_qty`, `stock_value`

---

## 6. Dashboard 6 — Revenue Analysis

- **Target MongoDB Collection**: `revenue_analysis`
- **ERP Source Instance**: `http://erp.fpohub.com`
- **ERP DocType / Dataset**: `Purchase Invoice`
- **Source Type**: `doctype`
- **Sync Strategy**: `timestamp` (incremental watermarking)
- **Mapper Class**: `RevenueAnalysisMapper`

### Field Mapping Matrix

| Dashboard Field | Target Type | ERP Source Field | Transformation / Derivation | Status |
| :--- | :--- | :--- | :--- | :--- |
| `territory` | string | `territory` / `place_of_supply` / `shipping_address_display` / `company` | Resolved regional market territory | **Verified** |
| `month` | string | `posting_date` / `bill_date` | Abbreviated month string (e.g. `"Jun"`, `"Dec"`) | **Verified** |
| `purchase_amount` | float | `grand_total` / `net_total` | Summed monthly procurement value | **Verified** |
| `sales_amount` | float (nullable) | *None* | Set to `null` (Purchase Invoice represents procurement only) | **Unavailable (Null)** |

### Aggregation Rules
- **Group By**: `["territory", "month"]`
- **Sum**: `purchase_amount`
