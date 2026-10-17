# Dashboard 3 — Farmer Income & Visits Mapping Specification

- **Target MongoDB Collection**: `farmer_income_visits`
- **ERP Source Instance**: `http://erp.csa-india.org`
- **ERP DocType / Dataset**: `CC Daily Reports` (child table `consolidated_report`)
- **Source Type**: `doctype`
- **Sync Strategy**: `timestamp` (incremental watermarking)
- **Mapper Class**: `FarmerIncomeVisitsMapper`

## Field Mapping Matrix

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

## Aggregation Rules
- **Group By**: `["coordinator_name", "month", "village"]`
- **Sum**: `farmers_met`, `visits`, `score`
