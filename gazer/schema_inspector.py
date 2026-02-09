from db_connector import DBConnector # TODO: Relative import without leading dot — use `from .db_connector import DBConnector`

class SchemaInspector:
  def __init__(self, DBConnector): # TODO: Parameter name `DBConnector` shadows the class import on line 1 — rename to `db_connector` or `db` to avoid confusion
    self.db = DBConnector
    self._cache = {}
  
  # Tables
  def get_tables(self):
    if 'tables' not in self._cache:
      self._cache['tables'] = self.fetch_tables()
    return self._cache['tables']
  
  def fetch_tables(self):
    query = """
      SELECT table_name
      FROM information_schema.tables
      WHERE table_schema = 'bdidata'
      ORDER BY table_name
    """ # TODO: Schema name 'bdidata' is hardcoded in multiple queries — extract to a class-level constant or constructor parameter
    results = self.db.execute_query_raw(query)
    tables = [row[0] for row in results]
    return tables
  
  # Columns
  def get_columns(self, table_name):
    cache_key = f'columns_{table_name}'
    if cache_key not in self._cache:
      self._cache[cache_key] = self.fetch_columns(table_name)
    return self._cache[cache_key]
  
  def fetch_columns(self, table_name):
    # TODO: No error handling — if the table doesn't exist or the DB connection drops, the raw psycopg2 exception will propagate unhandled
    query = """
      SELECT
          c.column_name,
          c.data_type,
          c.is_nullable,
          c.column_default,
          c.udt_name,
          -- Check if it's a primary key
          CASE WHEN pk.column_name IS NOT NULL THEN true ELSE false END as is_primary_key,
          -- Check if it's a foreign key
          CASE WHEN fk.column_name IS NOT NULL THEN true ELSE false END as is_foreign_key,
          -- Get foreign key reference if it exists
          fk.foreign_table_name,
          fk.foreign_column_name
      FROM information_schema.columns c
      -- Join to get primary key info
      LEFT JOIN (
          SELECT ku.table_name, ku.column_name
          FROM information_schema.table_constraints tc
          JOIN information_schema.key_column_usage ku
              ON tc.constraint_name = ku.constraint_name
              AND tc.table_schema = ku.table_schema
          WHERE tc.constraint_type = 'PRIMARY KEY'
              AND tc.table_schema = 'bdidata'
      ) pk ON c.table_name = pk.table_name AND c.column_name = pk.column_name
      -- Join to get foreign key info
      LEFT JOIN (
          SELECT
              ku.table_name,
              ku.column_name,
              ccu.table_name AS foreign_table_name,
              ccu.column_name AS foreign_column_name
          FROM information_schema.table_constraints tc
          JOIN information_schema.key_column_usage ku
              ON tc.constraint_name = ku.constraint_name
              AND tc.table_schema = ku.table_schema
          JOIN information_schema.constraint_column_usage ccu
              ON tc.constraint_name = ccu.constraint_name
              AND tc.table_schema = ccu.table_schema
          WHERE tc.constraint_type = 'FOREIGN KEY'
              AND tc.table_schema = 'bdidata'
      ) fk ON c.table_name = fk.table_name AND c.column_name = fk.column_name
      WHERE c.table_schema = 'bdidata' AND c.table_name = %s
      ORDER BY c.ordinal_position
    """
    results = self.db.execute_query_raw(query, (table_name,))
    columns = []
    for row in results: # TODO: Accessing columns by numeric index (row[0], row[1], etc.) is fragile — if the query changes, all indices silently break. Consider using a dict cursor or named constants
      col = {
        'name': row[0],
        'type': row[1],
        'nullable': row[2] == 'YES',
        'default': row[3],
        'udt_name': row[4],  # User-defined type (for enums)
        'is_primary_key': row[5],
        'is_foreign_key': row[6],
      }
      # Add foreign key reference if exists
      if row[6]:
        col['fk_table'] = row[7]
        col['fk_column'] = row[8]
      columns.append(col)
    return columns
  
  # Enums
  def get_enum_values(self, enum_type_name):
    cache_key = f'enum_{enum_type_name}'
    if cache_key not in self._cache:
      self._cache[cache_key] = self.fetch_enum_values(enum_type_name)
    return self._cache[cache_key]
  
  def fetch_enum_values(self, enum_type_name):
    query = """
        SELECT e.enumlabel
        FROM pg_type t 
        JOIN pg_enum e ON t.oid = e.enumtypid  
        WHERE t.typname = %s
        ORDER BY e.enumsortorder
    """
    results = self.db.execute_query_raw(query, (enum_type_name,))
    enum_values = [row[0] for row in results]
    return enum_values
  
  def get_table_enums(self, table_name):
    """Get all enum columns for a table with their possible values.
    Returns:
        dict: {column_name: [enum_values]}
    """
    columns = self.get_columns(table_name)
    enums = {}
    for col in columns:
      if col['type'] == 'USER-DEFINED':
        enum_type = col['udt_name']
        enum_values = self.get_enum_values(enum_type)
        if enum_values:  # Only include if we found values
          enums[col['name']] = enum_values
    return enums
  
  # Utils
  def refresh_cache(self, scope=None):
    """Refresh cached schema information.
    Args:
        scope: 'tables', 'columns', 'enums', or None (refresh all)
    """
    if scope is None:
      self._cache.clear()
    elif scope == 'tables':
      self._cache = {k: v for k, v in self._cache.items() if not k.startswith('tables')}
    elif scope == 'columns':
      self._cache = {k: v for k, v in self._cache.items() if not k.startswith('columns_')}
    elif scope == 'enums':
      self._cache = {k: v for k, v in self._cache.items() if not k.startswith('enum_')}
