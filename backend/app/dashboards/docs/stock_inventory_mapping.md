# Dashboard 5 — Stock Inventory Mapping Specification

- **Target MongoDB Collection**: `stock_inventory`
- **ERP Source Instance**: `http://erp.fpohub.com`
- **ERP DocType / Dataset**: `Stock Balance`
- **Source Type**: `query_report`
- **Sync Strategy**: `snapshot` (fresh report execution replacement)
- **Mapper Class**: `StockInventoryMapper`

## Field Mapping Matrix

| Dashboard Field | Target Type | ERP Source Field | Transformation / Derivation | Status |
| :--- | :--- | :--- | :--- | :--- |
| `company` | string | `company` | Company name (e.g. `"Nelathalli Farmer Producer Company Limited"`) | **Verified** |
| `warehouse` | string | `warehouse` | Warehouse name (e.g. `"Vana parthy 1 - NFPCL"`) | **Verified** |
| `item_name` | string | `item_name` / `item_code` | Item title or item identifier | **Verified** |
| `item_group` | string | `item_group` | Item category (e.g. `"Farm Machinery"`, `"Produce"`) | **Verified** |
| `stock_qty` | float | `bal_qty` | Current balance quantity | **Verified** |
| `stock_value` | float | `bal_val` | Current balance valuation in INR | **Verified** |

## Aggregation Rules
- **Granularity**: Item and Warehouse level
- **Group By**: `["company", "warehouse", "item_name", "item_group"]`
- **Sum**: `stock_qty`, `stock_value`
