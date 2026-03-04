from __future__ import annotations

from textual.widgets import OptionList


class Autocomplete(OptionList):
  """Non-focusable autocomplete overlay.
  Shows a filtered list of string options. Knows nothing about schema,
  stages, or operators — the parent widget controls what is shown via
  set_options().
  """
  can_focus = False

  def set_options(self, options: list[str]) -> None:
    """Replace all options. Opens if non-empty, closes if empty."""
    self.clear_options()
    if options:
      for opt in options:
        self.add_option(opt)
      self.highlighted = 0
      self.open()
    else:
      self.close()

  def open(self) -> None:
    """Show by adding -dropdown-open class to parent."""
    if self.parent is not None:
      self.parent.add_class("-dropdown-open")

  def close(self) -> None:
    """Hide by removing -dropdown-open class from parent."""
    if self.parent is not None:
      self.parent.remove_class("-dropdown-open")

  @property
  def is_open(self) -> bool:
    return self.parent is not None and self.parent.has_class("-dropdown-open")

  def move_highlight(self, direction: int) -> None:
    """Move highlight up (-1) or down (+1)."""
    if self.option_count == 0:
      return
    if self.highlighted is None:
      self.highlighted = 0
    else:
      new = self.highlighted + direction
      if 0 <= new < self.option_count:
        self.highlighted = new

  def get_highlighted_value(self) -> str | None:
    """Return the string value of the highlighted option, or None."""
    if self.highlighted is None:
      return None
    option = self.get_option_at_index(self.highlighted)
    return str(option.prompt)
