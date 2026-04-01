import json
from datetime import datetime
from pathlib import Path


CACHE_DIR = Path.home() / ".gazer"
CACHE_FILE = CACHE_DIR / "schema_cache.json"


# Save / Load {{{
def save_cache(host: str, database: str,
               foreign_keys: list[dict],
               schema_data: list[dict] | None = None) -> None:
  """Save FK relationships and column schema to cache file."""
  data = {
    "host": host,
    "database": database,
    "timestamp": datetime.now().isoformat(),
    "foreign_keys": foreign_keys,
  }
  if schema_data is not None:
    data["schema_data"] = schema_data
  CACHE_DIR.mkdir(exist_ok=True)
  with open(CACHE_FILE, 'w') as f:
    json.dump(data, f, indent=2)


def load_cache(host: str, database: str,
               max_age_minutes: int = 10) -> dict | None:
  """Load cached schema if it matches the given host+database and is fresh.
  Returns:
    dict with 'foreign_keys' and optionally 'schema_data', or None.
  """
  if not CACHE_FILE.exists():
    return None
  try:
    with open(CACHE_FILE, 'r') as f:
      data = json.load(f)
    if data.get("host") != host or data.get("database") != database:
      return None
    ts = data.get("timestamp")
    if ts:
      age = datetime.now() - datetime.fromisoformat(ts)
      if age.total_seconds() > max_age_minutes * 60:
        return None
    return {
      "foreign_keys": data.get("foreign_keys", []),
      "schema_data": data.get("schema_data"),
    }
  except (json.JSONDecodeError, ValueError, KeyError):
    pass
  return None


def clear_cache() -> bool:
  """Delete the schema cache file. Returns True if a file was removed."""
  if CACHE_FILE.exists():
    CACHE_FILE.unlink()
    return True
  return False
# }}}
