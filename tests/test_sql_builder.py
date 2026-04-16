import pytest
from models.query_builder import build_sql

def test_build_sql_duckdb_simple():
    sql = build_sql(
        table="mrt_sales",
        db_type="duckdb",
        columns=["region", "revenue"]
    )
    assert sql == 'SELECT "region", "revenue" FROM "mrt_sales"'

def test_build_sql_bigquery_simple():
    sql = build_sql(
        table="project.dataset.table",
        db_type="bigquery",
        columns=["region", "revenue"]
    )
    assert sql == 'SELECT `region`, `revenue` FROM `project.dataset.table`'

def test_build_sql_aggregation():
    agg_columns = [
        {"col": "revenue", "func": "SUM", "alias": "total_rev"},
        {"col": "orders", "func": "COUNT", "alias": "order_count"}
    ]
    sql = build_sql(
        table="mrt_sales",
        db_type="duckdb",
        agg_columns=agg_columns,
        group_by=["region"]
    )
    assert 'SUM("revenue") AS "total_rev"' in sql
    assert 'COUNT("orders") AS "order_count"' in sql
    assert 'GROUP BY "region"' in sql

def test_build_sql_filters():
    filters = [
        {"col": "year", "op": "=", "val": 2023},
        {"col": "region", "op": "=", "val": "North"}
    ]
    sql = build_sql(
        table="mrt_sales",
        db_type="duckdb",
        filters=filters
    )
    assert "WHERE \"year\" = 2023 AND \"region\" = 'North'" in sql

def test_build_sql_limit_order():
    order_by = [{"col": "revenue", "dir": "DESC"}]
    sql = build_sql(
        table="mrt_sales",
        db_type="duckdb",
        order_by=order_by,
        limit=10
    )
    assert 'ORDER BY "revenue" DESC LIMIT 10' in sql

def test_build_sql_having():
    agg_columns = [{"col": "revenue", "func": "SUM", "alias": "total_rev"}]
    having = [{"col": "total_rev", "op": ">", "val": 1000}]
    sql = build_sql(
        table="mrt_sales",
        db_type="duckdb",
        agg_columns=agg_columns,
        group_by=["region"],
        having=having
    )
    assert 'HAVING "total_rev" > 1000' in sql

def test_build_sql_ctes():
    ctes = [{"name": "raw_filtered", "query": "SELECT * FROM sales WHERE amount > 0"}]
    sql = build_sql(
        table="raw_filtered",
        db_type="duckdb",
        ctes=ctes,
        columns=["customer_id"]
    )
    assert 'WITH "raw_filtered" AS (SELECT * FROM sales WHERE amount > 0)' in sql
    assert 'FROM "raw_filtered"' in sql

def test_build_sql_joins():
    joins = [{
        "table": "mrt_sales",
        "alias": "b",
        "on": "a.order_id = b.order_id AND a.product_id < b.product_id",
        "type": "INNER"
    }]
    sql = build_sql(
        table="mrt_sales AS a",
        db_type="duckdb",
        columns=["a.product_id", "b.product_id"],
        agg_columns=[{"col": "*", "func": "COUNT", "alias": "freq"}],
        joins=joins,
        group_by=["a.product_id", "b.product_id"]
    )
    assert 'FROM "mrt_sales" AS "a"' in sql
    assert 'INNER JOIN "mrt_sales" AS "b" ON a.order_id = b.order_id' in sql
    assert 'COUNT(*) AS "freq"' in sql
