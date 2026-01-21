from db_connector import DBConnector 

class SchemaInspector:
  def __init__(self, DBConnector):
    self.db = DBConnector
    self._cache = {}
  
  # Tables
  async def get_tables(self):
    if 'tables' not in self._cache:
      self._cache['tables'] = await self.fetch_tables()
    return self._cache['tables']
  
  async def fetch_tables(self):
    query = """
      SELECT table_name 
      FROM information_schema.tables 
      WHERE table_schema = 'bdidata'
      ORDER BY table_name
    """
    results = await self.db.execute_raw(query)
    tables = [row[0] for row in results]
    return tables
  
  # Columns
  async def get_columns(self, table_name):
    cache_key = f'columns_{table_name}'
    if cache_key not in self._cache:
      self._cache[cache_key] = await self.fetch_columns(table_name)
    return self._cache[cache_key]
  
  async def fetch_columns(self, table_name):
    query = """
      SELECT column_name,
             data_type,
             is_nullable,
             column_default,
             udt_name
      FROM information_schema.columns
      WHERE table_schema = 'bdidata' AND table_name = %s
      ORDER BY ordinal_position
    """
    results = await self.db.execute_raw(query, (table_name,))
    columns = []
    for row in results:
      columns.append({
        'name': row[0],
        'type': row[1],
        'nullable': row[2] == 'YES',
        'default': row[3],
        'udt_name': row[4]  # User-defined type (for enums)
      })
    return columns
  
  # Enums
  async def get_enum_values(self, enum_type_name):
    cache_key = f'enum_{enum_type_name}'
    if cache_key not in self._cache:
      self._cache[cache_key] = await self.fetch_enum_values(enum_type_name)
    return self._cache[cache_key]
  
  async def fetch_enum_values(self, enum_type_name):
    query = """
        SELECT e.enumlabel
        FROM pg_type t 
        JOIN pg_enum e ON t.oid = e.enumtypid  
        WHERE t.typname = %s
        ORDER BY e.enumsortorder
    """
    results = await self.db.execute_raw(query, (enum_type_name,))
    enum_values = [row[0] for row in results]
    return enum_values
  
  async def get_table_enums(self, table_name):
    """Get all enum columns for a table with their possible values.
    Returns:
        dict: {column_name: [enum_values]}
    """
    columns = await self.get_columns(table_name)
    enums = {}
    for col in columns:
      if col['type'] == 'USER-DEFINED':
        enum_type = col['udt_name']
        enum_values = await self.get_enum_values(enum_type)
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
