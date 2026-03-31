import argparse
import subprocess
import sys
import tempfile
import shutil
from pathlib import Path


DEFAULT_REPO_URL = "https://github.itap.purdue.edu/Nolte-Group/gazer.git"


def _confirm(prompt: str) -> bool:
  """Ask the user for y/n confirmation."""
  answer = input(f"{prompt} [y/N] ").strip().lower()
  return answer in ("y", "yes")


def _detect_installer() -> str:
  """Detect whether gazer was installed via pipx or conda."""
  try:
    result = subprocess.run(
      ["conda", "list", "gazer"], capture_output=True, text=True
    )
    if result.returncode == 0 and "gazer" in result.stdout:
      return "conda"
  except FileNotFoundError:
    pass
  return "pipx"


def _print_version() -> None:
  try:
    from importlib.metadata import version
    print(f"gazer {version('gazer')}")
  except Exception:
    print("gazer (version unknown — not installed as package)")


def _do_uninstall() -> None:
  installer = _detect_installer()

  if not _confirm(f"Uninstall gazer (installed via {installer})?"):
    print("Aborted.")
    return

  print(f"Uninstalling gazer via {installer}...")
  try:
    if installer == "conda":
      result = subprocess.run(["conda", "remove", "-y", "gazer"])
    else:
      result = subprocess.run(["pipx", "uninstall", "gazer"], cwd=tempfile.gettempdir())
  except FileNotFoundError:
    print(f"Error: {installer} not found.", file=sys.stderr)
    sys.exit(1)

  if result.returncode != 0:
    sys.exit(result.returncode)

  config_dir = Path.home() / ".gazer"
  if config_dir.exists():
    if _confirm(f"Remove config directory {config_dir}?"):
      shutil.rmtree(config_dir)
      print(f"Removed {config_dir}")
    else:
      print(f"Kept {config_dir}")

  print("Done.")


def _do_update(repo_url: str) -> None:
  print(f"Updating gazer from {repo_url}...")
  with tempfile.TemporaryDirectory() as tmpdir:
    clone_dir = str(Path(tmpdir) / "gazer_install")

    try:
      result = subprocess.run(["git", "clone", repo_url, clone_dir])
    except FileNotFoundError:
      print("Error: git not found. Install git first.", file=sys.stderr)
      sys.exit(1)
    if result.returncode != 0:
      print("Git clone failed.", file=sys.stderr)
      sys.exit(1)

    installer = _detect_installer()
    print(f"Installing with {installer}...")
    try:
      if installer == "conda":
        result = subprocess.run(
          ["conda", "install", "--use-local", clone_dir, "-y"]
        )
      else:
        result = subprocess.run(["pipx", "install", clone_dir, "--force"])
    except FileNotFoundError:
      print(f"Error: {installer} not found.", file=sys.stderr)
      sys.exit(1)
    sys.exit(result.returncode)


def main() -> None:
  parser = argparse.ArgumentParser(
    prog="gazer",
    description="Gazer — TUI database query builder for BDI Laboratory at Purdue.",
  )
  parser.add_argument("-v", "--version", action="store_true",
                      help="Print version and exit")
  parser.add_argument("--uninstall", action="store_true",
                      help="Uninstall gazer and remove ~/.gazer config")
  parser.add_argument("--update", nargs="?", const=DEFAULT_REPO_URL, default=None,
                      metavar="REPO_URL",
                      help="Update gazer from git (default: Purdue repo). "
                           "Optionally specify a custom repo URL.")
  parser.add_argument("--devmode", action="store_true",
                      help="Run in developer mode that gives access to the full schema, table-based selection, and hidden tables/columns")

  args = parser.parse_args()

  if args.version:
    _print_version()
    return
  if args.uninstall:
    _do_uninstall()
    return
  if args.update is not None:
    _do_update(args.update)
    return

  from .ui_main import main as run_app
  run_app(devmode=args.devmode)


if __name__ == "__main__":
  main()
