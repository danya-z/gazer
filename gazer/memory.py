import json
from pathlib import Path

class Config:
  """Manages configuration for Gazer, stored in ~/.gazer/config.json."""

  DEFAULTS = {
    "host": "ldvdbapgdb02a.itap.purdue.edu",
    "port": "5433",
    "database": "bdidata",
    "username": "",
  }

  def __init__(self):
    self._dir = Path.home() / ".gazer"
    self._dir.mkdir(exist_ok=True)
    self._config_file = self._dir / "config.json"
    self._load()

  def _load(self):
    """Load config from file, falling back to defaults if missing or corrupted."""
    if self._config_file.exists():
      try:
        with open(self._config_file, 'r') as f:
          self._data = json.load(f)
        return
      except (json.JSONDecodeError, ValueError):
        pass
    self._data = dict(self.DEFAULTS)
    self._save()

  def _save(self):
    """Save config to file."""
    with open(self._config_file, 'w') as f:
      json.dump(self._data, f, indent=2)

  def get_host(self):
    return self._data.get("host", self.DEFAULTS["host"])

  def get_port(self):
    return self._data.get("port", self.DEFAULTS["port"])

  def get_database(self):
    return self._data.get("database", self.DEFAULTS["database"])

  def get_username(self):
    return self._data.get("username", "")

  def set_username(self, username):
    self._data["username"] = username
    self._save()

  def update_connection_settings(self, host, port, database):
    """Update connection settings."""
    self._data["host"] = host
    self._data["port"] = port
    self._data["database"] = database
    self._save()
