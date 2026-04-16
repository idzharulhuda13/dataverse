"""
Query Builder Utility — Translates structured payloads into dialect-specific SQL.
"""
from typing import List, Dict, Any, Optional, Literal

def build_sql(
    table: str,
    db_type: Literal['duckdb', 'bigquery'],
    columns: List[str] = None,
    agg_columns: List[Dict[str, str]] = None,
    filters: List[Dict[str, Any]] = None,
    group_by: List[str] = None,
    order_by: List[Dict[str, str]] = None,
    having: List[Dict[str, Any]] = None,
    ctes: List[Dict[str, str]] = None,
    joins: List[Dict[str, Any]] = None,
    limit: Optional[int] = None
) -> str:
    """
    Constructs a SQL SELECT statement from structured parameters.
    
    Args:
        table: The table name or path (e.g. 'mrt_sales'). Can include alias ('mrt_sales AS s').
        db_type: Dialect to use ('duckdb' or 'bigquery').
        columns: List of raw columns to select.
        agg_columns: List of dicts like {'col': 'revenue', 'func': 'SUM', 'alias': 'total_revenue'}.
        filters: List of dicts like {'col': 'year', 'op': '=', 'val': 2023}.
        group_by: List of columns to group by.
        order_by: List of dicts like {'col': 'total_revenue', 'dir': 'DESC'}.
        having: List of dicts like {'col': 'total_revenue', 'op': '>', 'val': 1000}.
        ctes: List of dicts like {'name': 'cte_name', 'query': 'SELECT ...'}.
        joins: List of dicts like {'table': 'other_table', 'on': '...', 'type': 'LEFT', 'alias': 'o'}.
        limit: Max rows to return.
    """
    quote = '`' if db_type == 'bigquery' else '"'
    
    def quote_identifier(name: str) -> str:
        """Helper to quote names but preserve aliases and dots."""
        if not name or name == "*": return "*"
        
        # Handle aliases: "table AS t" -> "table" AS "t" (case insensitive detection)
        import re
        if re.search(r"\s+AS\s+", name, re.IGNORECASE):
            parts = re.split(r"\s+AS\s+", name, flags=re.IGNORECASE)
            return f"{quote_identifier(parts[0].strip())} AS {quote}{parts[1].strip()}{quote}"
            
        # Handle Dots: "schema.table" -> "schema"."table"
        if "." in name and db_type != 'bigquery':
            return ".".join([f"{quote}{p}{quote}" for p in name.split(".")])
        # BigQuery backticks for the whole name if it contains dots
        if "." in name and db_type == 'bigquery':
            return f"`{name}`"
        return f"{quote}{name}{quote}"

    # ── 1. WITH clause (CTEs) ────────────────────────────────────────────────
    cte_clause = ""
    if ctes:
        cte_parts = []
        for cte in ctes:
            name = cte['name']
            query = cte['query']
            cte_parts.append(f"{quote_identifier(name)} AS ({query})")
        cte_clause = "WITH " + ", ".join(cte_parts)
    
    # ── 2. SELECT clause ─────────────────────────────────────────────────────
    select_parts = []
    
    # Raw columns
    if columns:
        for c in columns:
            select_parts.append(quote_identifier(c))
            
    # Aggregations
    if agg_columns:
        for agg in agg_columns:
            col = agg['col']
            func = agg['func']
            alias = agg.get('alias', f"{func.lower()}_{col}")
            select_parts.append(f"{func}({quote_identifier(col)}) AS {quote_identifier(alias)}")
            
    if not select_parts:
        select_clause = "SELECT *"
    else:
        select_clause = f"SELECT {', '.join(select_parts)}"
        
    # ── 3. FROM clause ───────────────────────────────────────────────────────
    from_clause = f"FROM {quote_identifier(table)}"
            
    # ── 4. JOIN clause ───────────────────────────────────────────────────────
    join_clause = ""
    if joins:
        join_parts = []
        for j in joins:
            j_type = j.get('type', 'INNER').upper()
            j_table = j['table']
            j_alias = j.get('alias')
            j_on = j['on']
            
            table_spec = quote_identifier(j_table) if not j_alias else f"{quote_identifier(j_table)} AS {quote_identifier(j_alias)}"
            join_parts.append(f"{j_type} JOIN {table_spec} ON {j_on}")
        join_clause = " ".join(join_parts)

    # ── 5. WHERE clause ──────────────────────────────────────────────────────
    where_clause = ""
    if filters:
        filter_parts = []
        for f in filters:
            col = f['col']
            op = f['op']
            val = f['val']
            
            if isinstance(val, str):
                formatted_val = f"'{val}'"
            elif isinstance(val, bool):
                formatted_val = str(val).upper()
            elif val is None:
                op = 'IS' if op == '=' else 'IS NOT'
                formatted_val = 'NULL'
            else:
                formatted_val = str(val)
                
            filter_parts.append(f"{quote_identifier(col)} {op} {formatted_val}")
        where_clause = f"WHERE {' AND '.join(filter_parts)}"
        
    # ── 6. GROUP BY clause ───────────────────────────────────────────────────
    group_clause = ""
    if group_by:
        group_clause = f"GROUP BY {', '.join([quote_identifier(g) for g in group_by])}"
        
    # ── 7. HAVING clause ─────────────────────────────────────────────────────
    having_clause = ""
    if having:
        having_parts = []
        for h in having:
            col = h['col']
            op = h['op']
            val = h['val']
            
            fmt_val = f"'{val}'" if isinstance(val, str) else (str(val).upper() if isinstance(val, bool) else str(val))
            having_parts.append(f"{quote_identifier(col)} {op} {fmt_val}")
        having_clause = f"HAVING {' AND '.join(having_parts)}"

    # ── 8. ORDER BY clause ───────────────────────────────────────────────────
    order_clause = ""
    if order_by:
        order_parts = []
        for o in order_by:
            col = o['col']
            direction = o.get('dir', 'ASC')
            order_parts.append(f"{quote_identifier(col)} {direction}")
        order_clause = f"ORDER BY {', '.join(order_parts)}"
        
    # ── 9. LIMIT clause ──────────────────────────────────────────────────────
    limit_clause = f"LIMIT {limit}" if limit else ""
    
    # Combine
    sql = f"{cte_clause} {select_clause} {from_clause} {join_clause} {where_clause} {group_clause} {having_clause} {order_clause} {limit_clause}"
    return " ".join(sql.split()) # normalize whitespace
