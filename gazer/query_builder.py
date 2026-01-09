class QueryBuilder:
  def __init__(self):
    self.reset()

  def reset(self):
    self._table = None
    self._columns = []
    self._joins = []
    self._filters = []
    return self
    
  # ========== BUILDING BLOCKS ==========
    
  def set_table(self, table_name):
    """Add a table to SELECT"""
    self._table = table_name
    return self
    

  def add_column(self, column_name, table_name=None):
    """Add a column to SELECT.
    Args:
      column_name: Name of the column
      table_name: Optional table qualifier. 
        If None, uses unqualified column name
    """
    if table_name:
      full_column = f"{table_name}.{column_name}"
    else:
      full_column = column_name

    if full_column not in self._columns:
      self._columns.append(full_column)
      return self

  def add_columns(self, *columns):
    """Add multiple columns to SELECT.
    Args:
      columns: Can be strings ('col1', 'col2') 
      or tuples (('col1', 'table1'), ('col2', 'table2'))
    """
    for col in columns:
      if isinstance(col, tuple):
        self.add_column(col[0], col[1])
      else:
        self.add_column(col)
    return self
    
  def remove_column(self, column_name):
    """Remove a column from SELECT."""
    if column_name in self._columns:
      self._columns.remove(column_name)
    return self

  def add_join(self, table, on_clause, join_type='INNER'):
    """Add a JOIN clause.
    Args:
      table: Table to join
      on_clause: Join condition (e.g., 'wells.treatment_id = treatments.treatment_id')
      join_type: 'INNER', 'LEFT', 'RIGHT', 'FULL' (default: 'INNER')
    """
    self._joins.append({
      'table': table,
      'on': on_clause,
      'type': join_type.upper()
    })
    return self
  
  def add_auto_join(self, from_table, from_column, to_table, to_column, join_type='INNER'):
    """Add a JOIN with automatic ON clause generation.
    Args:
      from_table: Source table
      from_column: Foreign key column in source table
      to_table: Target table
      to_column: Primary key column in target table
      join_type: 'INNER', 'LEFT', 'RIGHT', 'FULL' (default: 'INNER')
    """
    on_clause = f"{from_table}.{from_column} = {to_table}.{to_column}"
    return self.add_join(to_table, on_clause, join_type)
  
  def remove_join(self, index):
    """Remove a join by index."""
    if 0 <= index < len(self._joins):
      self._joins.pop(index)
    return self
  
  def clear_joins(self):
    """Remove all joins."""
    self._joins = []
    return self
  
  def add_filter(self, column, operator, value, table_name=None):
    """Add a WHERE filter.
    Args:
      column: Column name
      operator: '=', '!=', '>', 'LIKE', 'IN', 'IS NULL', etc.
      value: The value to compare (None for 'IS NULL')
      table_name: Optional table qualifier for ambiguous columns
    Examples:
      .add_filter('treatment_name', '=', 'dmso')
      .add_filter('concentration', '>', 0.5)
      .add_filter('name', '=', 'John', table_name='researchers')
    """
    if table_name:
      full_column = f"{table_name}.{column}"
    else:
      full_column = column
        
    self._filters.append({
      'column': full_column,
      'operator': operator,
      'value': value
    })
    return self

  def remove_filter(self, index):
    """Remove a filter by index."""
    if 0 <= index < len(self._filters):
      self._filters.pop(index)
    return self
  
  def clear_filters(self):
    """Remove all filters."""
    self._filters = []
    return self
  
  # ========== QUERY GENERATION ==========
  
  def build(self):
    """Generate the SQL query string.
    Returns:
      str: The complete SQL query
    Raises ValueError if table or columns are not set
    """
    if not self._table:
      raise ValueError("Table must be set before building query")
    if not self._columns:
      raise ValueError("At least one column must be selected")
    
    # Build SELECT and JOIN clauses
    columns_str = ',\n       '.join(self._columns)
    sql = f"SELECT {columns_str}\nFROM {self._table}"
    if self._joins:
      for join in self._joins:
        join_type = join['type']
        table = join['table']
        on_clause = join['on']
        sql += f"\n{join_type} JOIN {table} ON {on_clause}"
    
    # Build WHERE clause
    if self._filters:
      conditions = []
      for f in self._filters:
        condition = self._format_filter(f)
        conditions.append(condition)
      where_clause = ' AND\n      '.join(conditions)
      sql += f"\nWHERE {where_clause}"

    sql += ";"
    return sql

  def _format_filter(self, filter_dict):
    """Format a single filter into SQL condition string.
    Args:
      filter_dict: {'column': str, 'operator': str, 'value': any}
    Returns:
      str: SQL condition (e.g., "treatment_name = 'dmso'")
    """
    column = filter_dict['column']
    operator = filter_dict['operator'].upper()
    value = filter_dict['value']
    
    # Handle NULL checks
    if operator in ('IS NULL', 'IS NOT NULL'):
      return f"{column} {operator}"
    
    # Handle IN operator
    if operator == 'IN':
      if not isinstance(value, (list, tuple)):
        value = [value]
      # Quote string values
      quoted_values = [self._quote_value(v) for v in value]
      values_str = ', '.join(quoted_values)
      return f"{column} IN ({values_str})"
      
    # Handle standard operators
    quoted_value = self._quote_value(value)
    return f"{column} {operator} {quoted_value}"
  
  def _quote_value(self, value):
    """Quote a value for SQL"""
    if value is None:
      return 'NULL'
    elif isinstance(value, str):
      escaped = value.replace("'", "''")
      return f"'{escaped}'"
    elif isinstance(value, bool):
      return 'TRUE' if value else 'FALSE'
    else:
      return str(value)
  
  # ========== UTILITY ==========
  
  def get_state(self):
    """Get current query state"""
    return {
      'table': self._table,
      'columns': self._columns.copy(),
      'joins': self._joins.copy(),
      'filters': self._filters.copy()
    }

  def __repr__(self):
    """String representation for debugging."""
    try:
      return self.build()
    except ValueError as e:
      return f"<QueryBuilder (incomplete): {e}>"
