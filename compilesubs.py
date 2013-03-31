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

  logfile_handler = logging.FileHandler(os.path.join(self_folder, "log.txt"), mode="w")
  logfile_formatter = logging.Formatter("%(asctime)s %(levelname)s (%(module)s): %(message)s", "%Y-%m-%d %H:%M:%S")
  logfile_handler.setFormatter(logfile_formatter)
  logger.addHandler(logfile_handler)

  # wx doesn't have a better exception mechanism.
  sys.excepthook = create_exception_handler(logger, None)

  # __main__ stuff is continued at the end of this file.


# Import everything else.
try:
  from datetime import datetime, timedelta
  import platform
  import re
  import urllib2

  from lib import common
  from lib import global_config
  from lib import snarkutils

except (Exception) as err:
  logging.exception(err)
  sys.exit(1)



def main_cli():
  config = None
  snarks = []

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

    snarkutils.process_snarks(config, snarks)
    if (len(snarks) == 0):
      raise common.CompileSubsException("After processing, no messages were left.")

    logging.info("Calling %s exporter..." % config.exporter_name)
    snarkutils.export_snarks(config, snarks)

    logging.info("Done.")

  except (common.CompileSubsException) as err:
    # Parser or Exporter failed in an uninteresting way.
    logging.error(str(err))
    sys.exit(1)

  except (Exception) as err:
    logging.exception(err)
    sys.exit(1)


def main():
  logging.info("CompileSubs %s (on %s)" % (global_config.VERSION, platform.platform(aliased=True, terse=False)))
  main_cli()



if __name__ == "__main__":
  global_config._settings_directory = self_folder
  main()
