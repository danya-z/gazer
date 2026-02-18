from __future__ import annotations

import os
from typing import TYPE_CHECKING, cast

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static, Input, DataTable, OptionList
from textual.widgets.option_list import Option

from .core_export import export_csv
from .mem_presets import load_presets, save_preset

if TYPE_CHECKING:
  from .ui_main import GazerApp


class ResultsScreen(ModalScreen): # {{{
  """Modal screen showing query results in a DataTable."""

  BINDINGS = [
    Binding("escape", "dismiss", "Dismiss", show=False),
    Binding("ctrl+x", "export", "Export CSV"),
  ]

  MAX_DISPLAY_ROWS = 100

  def __init__(self, sql: str, params: list, rows: list[dict]) -> None:
    super().__init__()
    self._params = params
    self._rows = rows

  def compose(self) -> ComposeResult:
    total = len(self._rows)
    if total > self.MAX_DISPLAY_ROWS:
      count_text = f"Showing {self.MAX_DISPLAY_ROWS} of {total} rows"
    else:
      count_text = f"{total} rows"

    with Vertical(id="results-box"):
      yield Static(count_text, id="results-count")
      yield DataTable(id="results-table")
      yield Static("'ctrl+s' export | 'escape' dismiss", classes="hint")

  def on_mount(self) -> None:
    table = self.query_one("#results-table", DataTable)
    if not self._rows:
      return
    for key in self._rows[0].keys():
      table.add_column(str(key), key=str(key))
    for row in self._rows[:self.MAX_DISPLAY_ROWS]:
      table.add_row(*[str(v) for v in row.values()])

  def action_dismiss(self) -> None:
    self.dismiss()

  def action_export(self) -> None:
    self.app.push_screen(ExportDialog(self._rows))
# }}}


class ExportDialog(ModalScreen): # {{{
  """Modal dialog that asks for a file path, then exports query results to CSV."""

  BINDINGS = [
    Binding("escape", "dismiss", "Cancel", show=False),
  ]

  def __init__(self, rows: list[dict]) -> None:
    super().__init__()
    self._rows = rows

  def compose(self) -> ComposeResult:
    with Vertical(id="export-box"):
      yield Static("Export to CSV", id="export-title")
      yield Static(f"{len(self._rows)} rows to export", classes="export-info")
      yield Input(
        placeholder="Enter file path (e.g. ~/export.csv)",
        id="export-path"
      )
      yield Static("'enter' export | 'escape' cancel", classes="hint")

  def on_mount(self) -> None:
    path_input = self.query_one("#export-path", Input)
    app = cast("GazerApp", self.app)
    default_dir = app.config.get_export_path()
    if default_dir:
      prefill = default_dir.rstrip("/") + "/"
      path_input.value = prefill
      path_input.cursor_position = len(prefill)
    path_input.focus()

  def on_input_submitted(self, event: Input.Submitted) -> None:
    """Export when the user presses Enter on the file path input."""
    filepath = os.path.expanduser(event.value.strip())
    if not filepath:
      return

    if not filepath.endswith(".csv"):
      self.query_one(".hint", Static).update("File must end with .csv")
      return

    parent = os.path.dirname(filepath)
    if not parent or not os.path.isdir(parent):
      self.query_one(".hint", Static).update(f"Directory does not exist: {parent or filepath}")
      return

    try:
      count = export_csv(self._rows, filepath)
      app = cast("GazerApp", self.app)
      app.config.set_export_path(os.path.dirname(event.value.strip()))
      self.query_one(".hint", Static).update(f"Exported {count} rows to {filepath}")
    except Exception as e:
      self.query_one(".hint", Static).update(f"Export failed: {e}")

  def action_dismiss(self) -> None:
    self.dismiss()
# }}}


class PresetPicker(ModalScreen): # {{{
  """Modal screen for loading a column preset."""

  BINDINGS = [
    Binding("escape", "dismiss", "Cancel", show=False),
  ]

  def __init__(self) -> None:
    super().__init__()
    self._presets = load_presets()

  def compose(self) -> ComposeResult:
    with Vertical(id="preset-picker-box"):
      yield Static("Load Preset", id="preset-picker-title")
      yield OptionList(id="preset-list")
      yield Static("'enter' load | 'escape' cancel", classes="hint")

  def on_mount(self) -> None:
    option_list = self.query_one("#preset-list", OptionList)
    for name in self._presets:
      cols = ", ".join(self._presets[name])
      option_list.add_option(Option(f"{name}  ({cols})", id=name))
    if not self._presets:
      self.query_one(".hint", Static).update("No presets saved yet")

  def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
    name = str(event.option_id)
    columns = self._presets.get(name, [])
    self.dismiss(columns)

  def action_dismiss(self) -> None:
    self.dismiss(None)
# }}}


class PresetSaver(ModalScreen): # {{{
  """Modal screen for saving the current columns as a preset."""

  BINDINGS = [
    Binding("escape", "dismiss", "Cancel", show=False),
  ]

  def __init__(self, columns: list[str]) -> None:
    super().__init__()
    self._columns = columns

  def compose(self) -> ComposeResult:
    cols_text = ", ".join(self._columns) if self._columns else "(no columns)"
    with Vertical(id="preset-saver-box"):
      yield Static("Save Preset", id="preset-saver-title")
      yield Static(f"Columns: {cols_text}", id="preset-columns")
      yield Input(placeholder="Preset name", id="preset-name")
      yield Static("'enter' save | 'escape' cancel", classes="hint")

  def on_mount(self) -> None:
    self.query_one("#preset-name", Input).focus()

  def on_input_submitted(self, event: Input.Submitted) -> None:
    name = event.value.strip()
    if not name:
      return
    existing = load_presets()
    save_preset(name, self._columns)
    hint = self.query_one(".hint", Static)
    if name in existing:
      hint.update(f"Overwrote preset '{name}'")
    else:
      hint.update(f"Saved preset '{name}'")

  def action_dismiss(self) -> None:
    self.dismiss(None)
# }}}
