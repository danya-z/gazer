from gazer.query_builder import QueryBuilder

def test_query_builder():
  """Test QueryBuilder without database."""
  print("=" * 60)
  print("TEST 1: Simple SELECT")
  print("=" * 60)

  qb = QueryBuilder()
  qb.set_table('treatments')
  qb.add_columns('treatment_name', 'concentration')
  qb.add_filter('treatment_name', '=', 'dmso')

  sql = qb.build()
  print(sql)
  print()

  # Expected output:
  # SELECT treatment_name, concentration
  # FROM treatments
  # WHERE treatment_name = 'dmso';

  print("=" * 60)
  print("TEST 2: JOIN with qualified columns")
  print("=" * 60)

  qb = QueryBuilder()
  qb.set_table('wells')
  qb.add_column('well_id', 'wells')
  qb.add_column('treatment_name', 'treatments')
  qb.add_auto_join('wells', 'treatment_id', 'treatments', 'treatment_id')
  qb.add_filter('treatment_name', '=', 'DMSO', table_name='treatments')

  sql = qb.build()
  print(sql)
  print()

  # Expected output:
  # SELECT wells.well_id, treatments.treatment_name
  # FROM wells
  # INNER JOIN treatments ON wells.treatment_id = treatments.treatment_id
  # WHERE treatments.treatment_name = 'DMSO';

  print("=" * 60)
  print("TEST 3: Multiple JOINs")
  print("=" * 60)

  qb = QueryBuilder()
  qb.set_table('wells')
  qb.add_column('well_id', 'wells')
  qb.add_column('treatment_name', 'treatments')
  qb.add_column('name', 'researchers')
  qb.add_auto_join('wells', 'treatment_id', 'treatments', 'treatment_id')
  qb.add_auto_join('wells', 'plate_id', 'plates', 'plate_id')
  qb.add_auto_join('plates', 'researcher_id', 'researchers', 'researcher_id')

  sql = qb.build()
  print(sql)
  print()


  print("=" * 60)
  print("TEST 4: Complex filters")
  print("=" * 60)

  qb = QueryBuilder()
  qb.set_table('treatments')
  qb.add_columns('treatment_name', 'concentration', 'treatment_type')
  qb.add_filter('treatment_type', 'IN', ['drug', 'vehicle'])
  qb.add_filter('concentration', '>', 0.5)
  qb.add_filter('deleted_at', 'IS NULL', None)

  sql = qb.build()
  print(sql)
  print()

  print("=" * 60)
  print("TEST 5: Query state inspection")
  print("=" * 60)

  qb = QueryBuilder()
  qb.set_table('biopsies')
  qb.add_columns('biopsy_id', 'patient_type')
  qb.add_filter('patient_type', '=', 'human')

  state = qb.get_state()
  print(f"Table: {state['table']}")
  print(f"Columns: {state['columns']}")
  print(f"Filters: {state['filters']}")
  print()

if __name__ == '__main__':
  test_query_builder()
