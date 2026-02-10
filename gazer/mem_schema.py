import json
from pathlib import Path
from datetime import datetime


CACHE_FILE = Path.home() / ".gazer" / "schema_cache.json"


def save_cache(host, database, foreign_keys):
  """Save FK relationships to cache file."""
  data = {
    "host": host,
    "database": database,
    "timestamp": datetime.now().isoformat(),
    "foreign_keys": foreign_keys,
  }
  CACHE_FILE.parent.mkdir(exist_ok=True)
  with open(CACHE_FILE, 'w') as f:
    json.dump(data, f, indent=2)


def load_cache(host, database):
  """Load cached FK relationships if they match the given host+database.
  Returns:
    list[dict] or None: FK list if cache is valid, None otherwise.
  """
  if not CACHE_FILE.exists():
    return None
  try:
    with open(CACHE_FILE, 'r') as f:
      data = json.load(f)
    if data.get("host") == host and data.get("database") == database:
      return data.get("foreign_keys")
  except (json.JSONDecodeError, ValueError, KeyError):
    pass
  return None
