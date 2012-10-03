#!/usr/bin/env python

from datetime import datetime, timedelta
import locale
import logging
import os
import platform
import re
import sys
import urllib2

from lib import common
from lib import global_config
from lib import snarkutils


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

  main()
