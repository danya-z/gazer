import json
from pathlib import Path


PRESETS_FILE = Path.home() / ".gazer" / "presets.json"
DEFAULT_PRESET = """{
  "presets": {
    "Standard Out": [
      "wells.plate_id",
      "wells.well_number",
      "tissues.cell_line",
      "tissues.growth_method",
      "treatments.treatment_name",
      "treatments.concentration",
      "wells.t0",
      "wells.tf",
      "wells.dt",
      "wells.f1",
      "wells.f2",
      "wells.channel",
      "wells.comments"
    ]
  }
}"""

# Load / Save {{{
def load_presets() -> dict[str, list[str]]:
  """Load all presets from file. Returns empty dict on missing/corrupted file."""
  if not PRESETS_FILE.exists():
    with open(PRESETS_FILE, 'w') as f:
      f.write(DEFAULT_PRESET)
  try:
    with open(PRESETS_FILE, 'r') as f:
      data = json.load(f)
    return data.get("presets", {})
  except (json.JSONDecodeError, ValueError, KeyError):
    return {}


def save_presets(presets: dict[str, list[str]]) -> None:
  """Save all presets to file."""
  PRESETS_FILE.parent.mkdir(exist_ok=True)
  with open(PRESETS_FILE, 'w') as f:
    json.dump({"presets": presets}, f, indent=2)


def save_preset(name: str, columns: list[str]) -> None:
  """Save or overwrite a single preset."""
  presets = load_presets()
  presets[name] = columns
  save_presets(presets)


def delete_preset(name: str) -> None:
  """Delete a preset by name. No-op if it doesn't exist."""
  presets = load_presets()
  presets.pop(name, None)
  save_presets(presets)
# }}}
