from lib import cleanup


# Global constants.

VERSION = "3.52"

_settings_dir = "."
_cleanup_handler = cleanup.CustomCleanupHandler()

def get_settings_dir():
  """Returns a path to a directory where settings can be stored.
  No assumptions should be made about being absolute/relative,
  trailing slash, or slash type.
  """
  return _settings_dir

def get_cleanup_handler():
  """Returns a globally accessable cleanup handler."""
  return _cleanup_handler

def keeping_alive():
  """Pollable boolean that returns True to interrupt, false otherwise."""
  try:
    return _cleanup_handler.is_not_cleaning()
  except (AttributeError) as err:
    return True

def nap(seconds):
  """Sleep N seconds in an interruptable manner."""
  try:
    _cleanup_handler.nap(seconds)
  except (AttributeError) as err:
    time.sleep(seconds)
