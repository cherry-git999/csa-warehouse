# Dashboard 1 — NF Coordinator Performance Mapping Specification

- **Target MongoDB Collection**: `nf_coordinator_activities`
- **ERP Source Instance**: `http://erp.csa-india.org`
- **ERP DocType / Dataset**: `CC Daily Reports`
- **Source Type**: `doctype`
- **Sync Strategy**: `timestamp` (incremental watermarking)
- **Mapper Class**: `NFCoordinatorMapper`

## Field Mapping Matrix

| Dashboard Field | Target Type | ERP Source Field | Transformation / Derivation | Status |
| :--- | :--- | :--- | :--- | :--- |
| `coordinator_name` | string | `parent.name_of_nf_coordinator` | Extracted from parent document or row owner | **Verified** |
| `district` | string | `child.mandal` / `child.village` / `child.name_of_the_fpo` / `parent.district` | Extracted from activity location fields; fallback to `"General"` | **Verified** |
| `date` | string (`DD-MM-YYYY`) | `child.date` / `parent.creation` | Converted via `normalize_date()` into `DD-MM-YYYY` | **Verified** |
| `type_of_activity` | string | `child.activity` / `child.sub_activity` | Extracted from child tables `field_visit` and `cc_daily_reports` | **Verified** |
| `planned_activities`| integer | Activity event instance | Aggregated event count per coordinator/date/type | **Verified** |
| `actual_activities` | integer | Activity event instance | Aggregated event count per coordinator/date/type | **Verified** |
| `total_score` | integer | Derived (`actual_activities * 10`) | Evaluated activity score | **Derived** |

## Aggregation Rules
- **Group By**: `["coordinator_name", "district", "date", "type_of_activity"]`
- **Sum**: `planned_activities`, `actual_activities`, `total_score`
