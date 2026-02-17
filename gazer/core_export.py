import csv


def export_csv(rows: list[dict], filepath: str) -> int:
  """Export query results to a CSV file.
  Args:
    rows: list of DictCursor row dicts
    filepath: path to write the CSV to
  Returns:
    number of rows written
  """
  if not rows:
    return 0

  fieldnames = list(rows[0].keys())

  with open(filepath, 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
      writer.writerow(dict(row))

  return len(rows)
