#!/usr/bin/env python

from datetime import datetime, timedelta
import locale
import logging
import os
import platform
import re
import sys
import urllib2
import wx

from lib import cleanup
from lib import common
from lib import global_config
from lib import snarkutils
from lib.gui import csgui


def main_gui():
  config = None
  snarks = []

  logging.info("Registering ctrl-c handler.")
  cleanup_handler = cleanup.CustomCleanupHandler()
  cleanup_handler.register()  # Must be called from main thread.
  # Warning: If the main thread gets totally blocked, it'll never notice sigint.
  sys.excepthook = create_exception_handler(logger, cleanup_handler)

  try:
    # If common's backend prompt funcs were to be replaced
    # (i.e., for GUI popups), that'd happen here.

    # Import the config module as an object that can
    # be passed around, and suppress creation of pyc clutter.
    #
    sys.dont_write_bytecode = True
    config = __import__("config")
    sys.dont_write_bytecode = False
    config = common.Changeling(config)  # A copy w/o module baggage.

    logging.info("Calling %s parser..." % config.parser_name)
    snarks = snarkutils.parse_snarks(config)
    if (len(snarks) == 0):
      raise common.CompileSubsException("No messages were parsed.")

    snarkutils.gui_preprocess_snarks(config, snarks)
    snarkutils.gui_fudge_users(config, snarks)

    if (len(snarks) == 0):
      raise common.CompileSubsException("After preprocessing, no messages were left.")

    snarks_wrapper = common.SnarksWrapper(config, snarks)

    fudge_saver = common.Bunch()
    def on_snarks_changed(e):
      if (common.SnarksEvent.FLAG_CONFIG_FUDGES not in e.get_flags()):
        return

      repr_str = snarkutils.config_repr(e.get_source().clone_config())
      with open("./config_gui_backup.py", "w") as fudge_file:
        fudge_file.write("# These settings were auto-saved when the GUI made changes.\n")
        fudge_file.write("# To reuse them next time, rename this file to config.py.\n")
        fudge_file.write("# Otherwise this file will be overwritten.\n\n")
        fudge_file.write(repr_str)
        fudge_file.write("\n")
    fudge_saver.on_snarks_changed = on_snarks_changed
    snarks_wrapper.add_snarks_listener(fudge_saver)

    mygui = csgui.GuiApp(snarks_wrapper=snarks_wrapper, redirect=False, clearSigInt=False)
    cleanup_handler.add_gui(mygui)

    try:
      mygui.MainLoop()
    finally:
      mygui.done = True

  except (common.CompileSubsException) as err:
    # Parser or Exporter failed in an uninteresting way.
    logging.error(str(err))

  except (Exception) as err:
    logging.exception(err)

  finally:
    cleanup_handler.cleanup()


def main():
  logging.info("CompileSubs %s (on %s)" % (global_config.VERSION, platform.platform(aliased=True, terse=False)))
  main_gui()


def create_exception_handler(logger, cleanup_handler):
  # The logger is protected from garbage collection by closure magic.
  # Local vars referenced by inner funcs live as long as those funcs.
  def handleException(type, value, tb):
    logger.error("Uncaught exception", exc_info=(type, value, tb))
    if (cleanup_handler is not None):
      cleanup_handler.cleanup()
    else:
      sys.exit(1)
  return handleException



if __name__ == "__main__":
  locale.setlocale(locale.LC_ALL, "")

  # Go to the script dir (primary module search path; blank if cwd).
  if (sys.path[0]): os.chdir(sys.path[0])

  logger = logging.getLogger()
  logger.setLevel(logging.DEBUG)

  logstream_handler = logging.StreamHandler()
  logger.addHandler(logstream_handler)
  logstream_formatter = logging.Formatter("%(levelname)s (%(module)s): %(message)s")
  logstream_handler.setFormatter(logstream_formatter)
  logstream_handler.setLevel(logging.INFO)

  logfile_handler = logging.FileHandler("./log.txt", mode="w")
  logger.addHandler(logfile_handler)
  logfile_formatter = logging.Formatter("%(asctime)s %(levelname)s (%(module)s): %(message)s", "%Y-%m-%d %H:%M:%S")
  logfile_handler.setFormatter(logfile_formatter)

  # wx doesn't have a better exception mechanism.
  sys.excepthook = create_exception_handler(logger, None)

  main()
