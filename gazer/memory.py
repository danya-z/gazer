import json
from pathlib import Path

class Config:
  """Manages configuration and cache for Gazer."""

  def __init__(self):
    # Store config and cache in gazer's memory directory
    mem_dir = Path(__file__).parent.parent / "mem" # TODO: Fragile path resolution — assumes the package is always two levels deep from the mem/ directory. Breaks if the package is installed as a proper Python package. Consider using a config directory relative to the user's home (e.g., ~/.config/gazer/) or making mem_dir configurable
    self.config_file = mem_dir / "config.json"
    self.cache_file = mem_dir / "cache.json"

    # Load or create config
    self._load_config()
    self._load_cache()
  
  def _load_config(self):
    """Load connection defaults from config file."""
    if self.config_file.exists():
      with open(self.config_file, 'r') as f:
        self.config = json.load(f) # TODO: No error handling for malformed JSON — json.JSONDecodeError will crash the app if config.json is corrupted
    else:
      # Default config
      self.config = {
        "host": "ldvdbapgdb02a.itap.purdue.edu",
        "port": "5433",
        "database": "bdidata"
      }
      self._save_config()
  
  def _save_config(self):
    """Save config to file."""
    with open(self.config_file, 'w') as f:
      json.dump(self.config, f, indent=2)
  
  def _load_cache(self):
    """Load cached username."""
    if self.cache_file.exists():
      with open(self.cache_file, 'r') as f:
        self.cache = json.load(f) # TODO: Same — no error handling for malformed JSON in cache file
    else:
      self.cache = {"username": ""}
  
  def _save_cache(self):
    """Save cache to file."""
    with open(self.cache_file, 'w') as f:
      json.dump(self.cache, f, indent=2)
  
  def get_host(self):
    return self.config.get("host", "")
  
  def get_port(self):
    return self.config.get("port", "")
  
  def get_database(self):
    return self.config.get("database", "")
  
  def get_username(self):
    return self.cache.get("username", "")
  
  def set_username(self, username):
    self.cache["username"] = username
    self._save_cache()
  
  def update_connection_settings(self, host, port, database):
    """Update connection settings"""
    self.config["host"] = host
    self.config["port"] = port
    self.config["database"] = database
    self._save_config()
