"""Pipeline configuration for Territory Transactions (Purchase & Sales)."""

PIPELINE_ID = "territory_transactions"

CONFIG = {
    "erp_base_url": "http://erp.fpohub.com",
    "source_name": "Purchase Invoice",
    "source_type": "doctype",
    "sync_strategy": "timestamp",
    "identity_key": "date",
    "target_collection": "territory_transactions",
    "mapper": "TerritoryTransactionsMapper",
}
