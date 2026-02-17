import json
from pathlib import Path


class Config: # {{{
  """Manages configuration for Gazer, stored in ~/.gazer/config.json."""

  DEFAULTS: dict[str, str] = {
    "host": "ldvdbapgdb02a.itap.purdue.edu",
    "port": "5433",
    "database": "bdidata",
    "username": "",
    "export_path": "",
  }

  def __init__(self) -> None:
    self._dir = Path.home() / ".gazer"
    self._dir.mkdir(exist_ok=True)
    self._config_file = self._dir / "config.json"
    self._data: dict[str, str] = {}
    self._load()

  # Persistence {{{
  def _load(self) -> None:
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

  def _save(self) -> None:
    """Save config to file."""
    with open(self._config_file, 'w') as f:
      json.dump(self._data, f, indent=2)
  # }}}

  # Getters / Setters {{{
  def get_host(self) -> str:
    return self._data.get("host", self.DEFAULTS["host"])

  def get_port(self) -> str:
    return self._data.get("port", self.DEFAULTS["port"])

  def get_database(self) -> str:
    return self._data.get("database", self.DEFAULTS["database"])

  def get_username(self) -> str:
    return self._data.get("username", "")

  def set_username(self, username: str) -> None:
    self._data["username"] = username
    self._save()

  def get_export_path(self) -> str:
    return self._data.get("export_path", "")

  def set_export_path(self, path: str) -> None:
    self._data["export_path"] = path
    self._save()

  def update_connection_settings(self, host: str, port: str, database: str) -> None:
    """Update connection settings."""
    self._data["host"] = host
    self._data["port"] = port
    self._data["database"] = database
    self._save()
  # }}}
# }}}
