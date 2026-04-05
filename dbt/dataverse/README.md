# DataVerse dbt Project

dbt project managing all data warehouse models for the DataVerse platform.
Uses **DuckDB** as the warehouse engine via `dbt-duckdb`.

## Setup

```bash
# From the DataVerse root
uv run dbt run --profiles-dir .       # Build all models
uv run dbt test --profiles-dir .      # Run all tests
uv run dbt debug --profiles-dir .     # Verify connection
```

> Run all commands from inside `dbt/dataverse/` or prefix with `cd dbt/dataverse &&`.

## Project Structure

```
dbt/dataverse/
├── profiles.yml                  ← DuckDB connection (dataverse_warehouse.duckdb)
├── dbt_project.yml               ← Project config
└── models/
    └── chocolate_sales/          ← One folder per dataset domain
        ├── sources.yml           ← External parquet source definitions
        ├── src/                  ← Staging views (type casting only, no logic)
        ├── dim/                  ← Dimension tables (full refresh, schema.yml with PK tests)
        └── mrt/                  ← Data marts / OBTs (schema.yml with full docs + tests)
```

## Adding a New Dataset

1. Create `models/<dataset_name>/` with `src/`, `dim/`, `mrt/` subfolders
2. Add the new materialization config in `dbt_project.yml` under `models.dataverse.<dataset_name>:`
3. Add source parquet paths to `models/<dataset_name>/sources.yml`
4. Run `dbt run --select <dataset_name>` to build only the new dataset

## Warehouse

The compiled warehouse lives at `dbt/dataverse/dataverse_warehouse.duckdb` (gitignored — regenerate with `dbt run`).

| Schema | Layer | Contents |
|---|---|---|
| `main_chocolate_sales_src` | Staging views | Raw parquet reads, type-cast only |
| `main_chocolate_sales_dim` | Dimensions | Enriched reference tables |
| `main_chocolate_sales_mrt` | Marts (OBTs) | Analysis-ready tables for DataVerse agent |

## Data Tests

19 tests across `dim/` and `mrt/` layers (PK uniqueness + not_null + business logic).
Run with `uv run dbt test --profiles-dir .`
