from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any


ALLOWED_OPERATORS = {
  "=", "!=", "<>", "<", ">", "<=", ">=",
  "LIKE", "ILIKE", "NOT LIKE", "NOT ILIKE",
  "IN", "NOT IN",
  "IS NULL", "IS NOT NULL",
  "BETWEEN",
}

ALLOWED_JOIN_TYPES = {"INNER", "LEFT", "RIGHT", "FULL"}


# Filter {{{
@dataclass
class Filter:
  column: str
  operator: str
  value: Any = None

  def __post_init__(self) -> None:
    self.operator = self.operator.upper()
    if self.operator not in ALLOWED_OPERATORS:
      raise ValueError(
        f"Invalid operator '{self.operator}'. "
        f"Allowed: {', '.join(sorted(ALLOWED_OPERATORS))}"
      )
    if self.operator == "BETWEEN":
      if not isinstance(self.value, (list, tuple)) or len(self.value) != 2:
        raise ValueError(
          f"BETWEEN requires a 2-element list/tuple, got: {self.value!r}"
        )

  def build(self) -> tuple[str, list]:
    """Return (sql_fragment, params_list) with %s placeholders."""
    op = self.operator

    if op in ("IS NULL", "IS NOT NULL"):
      return f"{self.column} {op}", []

    if op in ("IN", "NOT IN"):
      """ We need to handle two somewhat discreet cases
        1. Weird or single value
          Filter("status", "IN", "a") → values = ["a"]
          Filter("status", "IN", 42) → values = [42]
        If not list, values will be wrapped into one as
        values = [self.value]

        2. List/tuple of values
          Filter("status", "IN", ["a", "b"]) → values = ["a", "b"]
        If list, we will just extract the list with
        values = list(self.value)
      """
      if not isinstance(self.value, (list, tuple)):
        values = [self.value]
      else:
        values = list(self.value)
      placeholders = ", ".join(["%s"] * len(values))
      return f"{self.column} {op} ({placeholders})", values

    if op == "BETWEEN":
      low, high = self.value
      return f"{self.column} BETWEEN %s AND %s", [low, high]

    return f"{self.column} {op} %s", [self.value]

  def __str__(self) -> str:
    op = self.operator
    if op in ("IS NULL", "IS NOT NULL"):
      return f"{self.column} {op}"
    if op in ("IN", "NOT IN"):
      vals = self.value if isinstance(self.value, (list, tuple)) else [self.value]
      return f"{self.column} {op} ({', '.join(repr(v) for v in vals)})"
    if op == "BETWEEN":
      return f"{self.column} BETWEEN {self.value[0]!r} AND {self.value[1]!r}"
    return f"{self.column} {op} {self.value!r}"
# }}}


# FilterGroup {{{
@dataclass
class FilterGroup:
  logic: str = "AND"
  children: list[Filter | FilterGroup] = field(default_factory=list)

  def __post_init__(self) -> None:
    self.logic = self.logic.upper()
    if self.logic not in ("AND", "OR"):
      raise ValueError(f"Logic must be 'AND' or 'OR', got '{self.logic}'")

  def add(self, child: Filter | FilterGroup) -> None:
    self.children.append(child)

  def remove(self, child: Filter | FilterGroup) -> None:
    self.children.remove(child)

  def is_empty(self) -> bool:
    return len(self.children) == 0

  def build(self) -> tuple[str, list]:
    """Recursively build (sql_fragment, params_list)."""
    if not self.children:
      return "", []

    parts: list[str] = []
    params: list = []
    for child in self.children:
      sql, child_params = child.build()
      if sql:
        parts.append(sql)
        params.extend(child_params)

    if not parts:
      return "", []

    if len(parts) == 1:
      return parts[0], params

    joiner = f" {self.logic} "      # E.g, " AND "
    combined = joiner.join(parts)   # E.g, "filter AND filter AND filter"
    return f"({combined})", params  # E.g, "(filter AND filter AND filter)", [params]
# }}}


# QueryBuilder {{{
class QueryBuilder:
  def __init__(self) -> None:
    self.reset()

  def reset(self) -> QueryBuilder:
    self._table: str | None = None
    self._columns: list[str] = []
    self._joins: list[dict] = []
    self._root_group = FilterGroup("AND")
    self._fk_graph: dict[str, list[dict]] = {}
    return self

  def set_foreign_keys(self, fk_list: list[dict]) -> QueryBuilder:
    """Store FK relationships and build adjacency graph.
    Args:
      fk_list: list of dicts with from_table, from_column, to_table, to_column
    """
    graph: dict[str, list[dict]] = defaultdict(list)
    for fk in fk_list:
      graph[fk['from_table']].append({
        'table': fk['to_table'],
        'from_col': fk['from_column'],
        'to_col': fk['to_column'],
      })
      graph[fk['to_table']].append({
        'table': fk['from_table'],
        'from_col': fk['to_column'],
        'to_col': fk['from_column'],
      })
    self._fk_graph = dict(graph)
    return self

  # Building Blocks {{{
  def set_table(self, table_name: str) -> QueryBuilder:
    self._table = table_name
    return self

  def add_column(self, column_name: str, table_name: str | None = None) -> QueryBuilder:
    if table_name:
      full_column = f"{table_name}.{column_name}"
    else:
      full_column = column_name

    if full_column not in self._columns:
      self._columns.append(full_column)
    return self

  def add_columns(self, *columns: str | tuple[str, str]) -> QueryBuilder:
    for col in columns:
      if isinstance(col, tuple):
        self.add_column(col[0], col[1])
      else:
        self.add_column(col)
    return self

  def remove_column(self, column_name: str) -> QueryBuilder:
    if column_name in self._columns:
      self._columns.remove(column_name)
    return self

  def add_join(self, table: str, on_clause: str, join_type: str = 'INNER') -> QueryBuilder:
    join_type = join_type.upper()
    if join_type not in ALLOWED_JOIN_TYPES:
      raise ValueError(
        f"Invalid join type '{join_type}'. "
        f"Allowed: {', '.join(sorted(ALLOWED_JOIN_TYPES))}"
      )
    self._joins.append({
      'table': table,
      'on': on_clause,
      'type': join_type,
    })
    return self

  def add_auto_join(self, from_table: str, from_column: str,
                    to_table: str, to_column: str,
                    join_type: str = 'INNER') -> QueryBuilder:
    on_clause = f"{from_table}.{from_column} = {to_table}.{to_column}"
    return self.add_join(to_table, on_clause, join_type)

  def remove_join(self, index: int) -> QueryBuilder:
    if 0 <= index < len(self._joins):
      self._joins.pop(index)
    return self

  def clear_joins(self) -> QueryBuilder:
    self._joins = []
    return self

  def add_filter(self, column: str, operator: str,
                 value: Any = None, table_name: str | None = None) -> QueryBuilder:
    if table_name:
      full_column = f"{table_name}.{column}"
    else:
      full_column = column

    f = Filter(full_column, operator, value)
    self._root_group.add(f)
    return self

  def add_filter_group(self, group: FilterGroup) -> QueryBuilder:
    self._root_group.add(group)
    return self

  def get_root_group(self) -> FilterGroup:
    return self._root_group

  def remove_filter(self, index: int) -> QueryBuilder:
    children = self._root_group.children
    if 0 <= index < len(children):
      children.pop(index)
    return self

  def clear_filters(self) -> QueryBuilder:
    self._root_group = FilterGroup("AND")
    return self
  # }}}

  # Auto-Join Resolution {{{
  def _get_referenced_tables(self) -> set[str]:
    """Collect all table names referenced in columns and filters."""
    tables: set[str] = set()
    for col in self._columns:
      if '.' in col:
        tables.add(col.split('.')[0])
    for child in self._root_group.children:
      if isinstance(child, Filter) and '.' in child.column:
        tables.add(child.column.split('.')[0])
    tables.discard(self._table)
    return tables

  def _find_all_paths(self, start: str, target: str,
                      visited: set[str] | None = None) -> list[list[tuple]]:
    """DFS to find all paths from start to target.
    Returns list of paths, where each path is a list of
    (from_table, from_col, to_table, to_col) tuples.
    """
    if visited is None:
      visited = set()
    visited = visited | {start}

    if start == target:
      return [[]]

    paths: list[list[tuple]] = []
    for edge in self._fk_graph.get(start, []):
      neighbor = edge['table']
      if neighbor in visited:
        continue
      step = (start, edge['from_col'], neighbor, edge['to_col'])
      for sub_path in self._find_all_paths(neighbor, target, visited):
        paths.append([step] + sub_path)
    return paths

  def _find_join_path(self, target: str) -> list[tuple]:
    """Find the unique FK path from self._table to target.
    Returns:
      list of (from_table, from_col, to_table, to_col) tuples.
    Raises ValueError if no path or multiple paths exist.
    """
    start = self._table
    if start == target:
      return []

    paths = self._find_all_paths(start, target)

    if len(paths) == 0:
      raise ValueError(f"No FK path from '{start}' to '{target}'")
    if len(paths) > 1:
      raise ValueError(
        f"Ambiguous FK path from '{start}' to '{target}': "
        f"found {len(paths)} paths"
      )
    return paths[0]

  def _resolve_joins(self) -> list[dict]:
    """Auto-add joins for tables referenced in columns/filters.
    Returns list of join dicts to use in build().
    """
    manually_joined = {j['table'] for j in self._joins}
    needed_tables = self._get_referenced_tables() - manually_joined

    if needed_tables and not self._fk_graph:
      raise ValueError(
        f"Columns reference other tables {needed_tables} "
        f"but no FK data is available. Call set_foreign_keys() first."
      )
    auto_joins: list[dict] = []

    already_joined = {self._table} | manually_joined
    for table in needed_tables:
      path = self._find_join_path(table)
      for from_table, from_col, to_table, to_col in path:
        if to_table not in already_joined:
          auto_joins.append({
            'table': to_table,
            'on': f"{from_table}.{from_col} = {to_table}.{to_col}",
            'type': 'LEFT',
          })
          already_joined.add(to_table)

    return list(self._joins) + auto_joins
  # }}}

  # Query Generation {{{
  def build(self) -> tuple[str, list]:
    """Generate the SQL query and params.
    Returns:
      tuple[str, list]: (sql_string with %s placeholders, params list)
    Raises ValueError if table or columns are not set.
    """
    if not self._table:
      raise ValueError("Table must be set before building query")
    if not self._columns:
      raise ValueError("At least one column must be selected")

    params: list = []

    columns_str = ",\n  ".join(self._columns)
    sql = f"SELECT\n  {columns_str}\nFROM {self._table}"

    all_joins = self._resolve_joins()
    for join in all_joins:
      sql += f"\n{join['type']} JOIN {join['table']} ON {join['on']}"

    if not self._root_group.is_empty():
      where_sql, where_params = self._root_group.build()
      if where_sql:
        sql += f"\nWHERE {where_sql}"
        params.extend(where_params)

    sql += ";"
    return sql, params
  # }}}

  # Utility {{{
  def get_state(self) -> dict:
    return {
      'table': self._table,
      'columns': self._columns.copy(),
      'joins': self._joins.copy(),
      'root_group': self._root_group,
    }

  def __repr__(self) -> str:
    try:
      sql, params = self.build()
      return f"{sql}  -- params: {params}"
    except ValueError as e:
      return f"<QueryBuilder (incomplete): {e}>"
  # }}}
# }}}
