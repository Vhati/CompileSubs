#!/usr/bin/env python

# Do some basic imports, and set up logging to catch ImportError.
import inspect
import logging
import locale
import os
import sys


def create_exception_handler(logger, cleanup_handler):
  # The logger is protected from garbage collection by closure magic.
  # Local vars referenced by inner funcs live as long as those funcs.
  def handle_exception(type, value, tb):
    logger.error("Uncaught exception", exc_info=(type, value, tb))
    if (cleanup_handler is not None):
      cleanup_handler.cleanup()
    else:
      sys.exit(1)
  return handle_exception


self_folder = "."  # This var will be used by multiple __main__ blocks.

if __name__ == "__main__":
  locale.setlocale(locale.LC_ALL, "")

  # Get the un-symlinked, absolute path to this module.
  self_folder = os.path.realpath(os.path.abspath(os.path.split(inspect.getfile( inspect.currentframe() ))[0]))
  if (self_folder not in sys.path): sys.path.insert(0, self_folder)

  # Add ./lib/ to the search path to appease 3rd party libs.
  lib_subfolder = os.path.realpath(os.path.abspath(os.path.join(os.path.split(inspect.getfile( inspect.currentframe() ))[0], "lib")))
  if (lib_subfolder not in sys.path): sys.path.insert(0, lib_subfolder)

  # Go to this module's dir.
  os.chdir(self_folder)

  logger = logging.getLogger()
  logger.setLevel(logging.DEBUG)

  logstream_handler = logging.StreamHandler()
  logstream_formatter = logging.Formatter("%(levelname)s (%(module)s): %(message)s")
  logstream_handler.setFormatter(logstream_formatter)
  logstream_handler.setLevel(logging.INFO)
  logger.addHandler(logstream_handler)

  logfile_handler = logging.FileHandler("./log.txt", mode="w")
  logfile_formatter = logging.Formatter("%(asctime)s %(levelname)s (%(module)s): %(message)s", "%Y-%m-%d %H:%M:%S")
  logfile_handler.setFormatter(logfile_formatter)
  logger.addHandler(logfile_handler)

  # wx doesn't have a better exception mechanism.
  sys.excepthook = create_exception_handler(logger, None)

  # __main__ stuff is continued at the end of this file.


# Import everything else (wx may be absent in some environments).
try:
  from datetime import datetime, timedelta
  import platform
  import re
  import urllib2
  import wx

  from lib import cleanup
  from lib import common
  from lib import global_config
  from lib import snarkutils
  from lib.gui import csgui

except (Exception) as err:
  logging.exception(err)
  sys.exit(1)



def main_gui():
  config = None
  snarks = []

  logging.info("Registering ctrl-c handler.")
  cleanup_handler = global_config.get_cleanup_handler()
  cleanup_handler.register()  # Must be called from main thread.
  # Warning: If the main thread gets totally blocked, it'll never notice sigint.
  sys.excepthook = create_exception_handler(logger, cleanup_handler)

  try:
    mygui = csgui.GuiApp(redirect=False, clearSigInt=False)
    cleanup_handler.add_gui(mygui)

    try:
      mygui.MainLoop()
    finally:
      mygui.done = True

  except (Exception) as err:
    logging.exception(err)

  finally:
    cleanup_handler.cleanup()


def main():
  logging.info("CompileSubs %s (on %s)" % (global_config.VERSION, platform.platform(aliased=True, terse=False)))
  main_gui()



if __name__ == "__main__":
  global_config._settings_directory = self_folder
  main()
