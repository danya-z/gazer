from __future__ import annotations

import os
from typing import TYPE_CHECKING, cast

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static, Input, DataTable

from .core_export import export_csv

if TYPE_CHECKING:
  from .ui_main import GazerApp


class ResultsScreen(ModalScreen): # {{{
  """Modal screen showing query results in a DataTable."""

  BINDINGS = [
    Binding("escape", "dismiss", "Dismiss", show=False),
    Binding("ctrl+s", "export", "Export CSV"),
  ]

  MAX_DISPLAY_ROWS = 500

  def __init__(self, sql: str, params: list, rows: list[dict]) -> None:
    super().__init__()
    self._sql = sql
    self._params = params
    self._rows = rows

  def compose(self) -> ComposeResult:
    total = len(self._rows)
    if total > self.MAX_DISPLAY_ROWS:
      count_text = f"Showing {self.MAX_DISPLAY_ROWS} of {total} rows"
    else:
      count_text = f"{total} rows"

    query_text = self._sql
    if self._params:
      query_text += f"\nParams: {self._params}"

    with Vertical(id="results-box"):
      yield Static(query_text, id="results-query")
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
