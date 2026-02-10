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


@dataclass
class Filter:
  column: str
  operator: str
  value: Any = None

  def __post_init__(self):
    self.operator = self.operator.upper()
    if self.operator not in ALLOWED_OPERATORS:
      raise ValueError(
        f"Invalid operator '{self.operator}'. "
        f"Allowed: {', '.join(sorted(ALLOWED_OPERATORS))}"
      )

  def build(self):
    """Return (sql_fragment, params_list) with %s placeholders."""
    op = self.operator

    if op in ("IS NULL", "IS NOT NULL"):
      return f"{self.column} {op}", []

    if op in ("IN", "NOT IN"):
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

  def __str__(self):
    op = self.operator
    if op in ("IS NULL", "IS NOT NULL"):
      return f"{self.column} {op}"
    if op in ("IN", "NOT IN"):
      vals = self.value if isinstance(self.value, (list, tuple)) else [self.value]
      return f"{self.column} {op} ({', '.join(repr(v) for v in vals)})"
    if op == "BETWEEN":
      return f"{self.column} BETWEEN {self.value[0]!r} AND {self.value[1]!r}"
    return f"{self.column} {op} {self.value!r}"


@dataclass
class FilterGroup:
  logic: str = "AND"
  children: list = field(default_factory=list)

  def __post_init__(self):
    self.logic = self.logic.upper()
    if self.logic not in ("AND", "OR"):
      raise ValueError(f"Logic must be 'AND' or 'OR', got '{self.logic}'")

  def add(self, child):
    self.children.append(child)

  def remove(self, child):
    self.children.remove(child)

  def is_empty(self):
    return len(self.children) == 0

  def build(self):
    """Recursively build (sql_fragment, params_list)."""
    if not self.children:
      return "", []

    parts = []
    params = []
    for child in self.children:
      sql, child_params = child.build()
      if sql:
        parts.append(sql)
        params.extend(child_params)

    if not parts:
      return "", []

    if len(parts) == 1:
      return parts[0], params

    joiner = f" {self.logic} "
    combined = joiner.join(parts)
    return f"({combined})", params


class QueryBuilder:
  def __init__(self):
    self.reset()

  def reset(self):
    self._table = None
    self._columns = []
    self._joins = []
    self._root_group = FilterGroup("AND")
    return self

  # Building Blocks

  def set_table(self, table_name):
    self._table = table_name
    return self

  def add_column(self, column_name, table_name=None):
    if table_name:
      full_column = f"{table_name}.{column_name}"
    else:
      full_column = column_name

    if full_column not in self._columns:
      self._columns.append(full_column)
    return self

  def add_columns(self, *columns):
    for col in columns:
      if isinstance(col, tuple):
        self.add_column(col[0], col[1])
      else:
        self.add_column(col)
    return self

  def remove_column(self, column_name):
    if column_name in self._columns:
      self._columns.remove(column_name)
    return self

  def add_join(self, table, on_clause, join_type='INNER'):
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

  def add_auto_join(self, from_table, from_column, to_table, to_column, join_type='INNER'):
    on_clause = f"{from_table}.{from_column} = {to_table}.{to_column}"
    return self.add_join(to_table, on_clause, join_type)

  def remove_join(self, index):
    if 0 <= index < len(self._joins):
      self._joins.pop(index)
    return self

  def clear_joins(self):
    self._joins = []
    return self

  def add_filter(self, column, operator, value=None, table_name=None):
    if table_name:
      full_column = f"{table_name}.{column}"
    else:
      full_column = column

    f = Filter(full_column, operator, value)
    self._root_group.add(f)
    return self

  def add_filter_group(self, group):
    self._root_group.add(group)
    return self

  def get_root_group(self):
    return self._root_group

  def remove_filter(self, index):
    children = self._root_group.children
    if 0 <= index < len(children):
      children.pop(index)
    return self

  def clear_filters(self):
    self._root_group = FilterGroup("AND")
    return self

  # Query Generation

  def build(self):
    """Generate the SQL query and params.
    Returns:
      tuple[str, list]: (sql_string with %s placeholders, params list)
    Raises ValueError if table or columns are not set.
    """
    if not self._table:
      raise ValueError("Table must be set before building query")
    if not self._columns:
      raise ValueError("At least one column must be selected")

    params = []

    columns_str = ',\n       '.join(self._columns)
    sql = f"SELECT {columns_str}\nFROM {self._table}"

    for join in self._joins:
      sql += f"\n{join['type']} JOIN {join['table']} ON {join['on']}"

    if not self._root_group.is_empty():
      where_sql, where_params = self._root_group.build()
      if where_sql:
        sql += f"\nWHERE {where_sql}"
        params.extend(where_params)

    sql += ";"
    return sql, params

  # Utility

  def get_state(self):
    return {
      'table': self._table,
      'columns': self._columns.copy(),
      'joins': self._joins.copy(),
      'root_group': self._root_group,
    }

  def __repr__(self):
    try:
      sql, params = self.build()
      return f"{sql}  -- params: {params}"
    except ValueError as e:
      return f"<QueryBuilder (incomplete): {e}>"
