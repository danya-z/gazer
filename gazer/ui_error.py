import platform

import pyperclip
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static


class ErrorOverlay(ModalScreen): # {{{
  """Modal error popup with dimmed background."""

  BINDINGS = [
    Binding("escape", "dismiss", "Dismiss", show=False),
    Binding("c", "copy_error", "Copy Error", show=False),
  ]

  def __init__(self, error_category: str, user_message: str,
               technical_details: str) -> None:
    super().__init__()
    self.error_category = error_category
    self.user_message = user_message
    self.technical_details = technical_details

  def compose(self) -> ComposeResult:
    with Vertical(id="error-box"):
      yield Static(f"{self.error_category} Error", id="error-title")
      yield Static(self.user_message, classes="user-error")
      yield Static("Technical Details:", classes="error-label")
      yield Static(self.technical_details, classes="technical-error")
      yield Static("'c' copy | 'escape' dismiss", id="error-hint", classes="hint")

  def action_dismiss(self) -> None:
    self.dismiss()

  def action_copy_error(self) -> None:
    hint = self.query_one("#error-hint", Static)
    try:
      pyperclip.copy(self.technical_details)
      hint.update("Copied to clipboard!")
    except pyperclip.PyperclipException:
      system = platform.system()
      if system == "Linux":
        msg = "Copy failed — try: sudo apt install xclip"
      elif system == "Darwin":
        msg = "Copy failed — try: brew install pbcopy"
      elif system == "Windows":
        msg = "Copy failed — clipboard access denied"
      else:
        msg = "Copy failed — no clipboard backend available"
      hint.update(msg)
# }}}
