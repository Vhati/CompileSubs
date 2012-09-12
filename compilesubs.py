#!/usr/bin/env python

from datetime import datetime, timedelta
import locale
import logging
import os
import random
import re
import sys
import urllib2

from lib import common


VERSION = "2.50"

random.seed()


def main():
  global VERSION

  try:
    logging.info("CompileSubs %s" % VERSION)

    # If common's backend prompt funcs were to be replaced
    # (i.e., for GUI popups), that'd happen here.

    # Import the config module as an object that can
    # be passed around, in case future fanciness replaces it.
    # Also suppress creation of pyc clutter.
    #
    sys.dont_write_bytecode = True
    config = __import__("config")
    sys.dont_write_bytecode = False

    logging.info("Calling %s parser..." % config.parser_name)
    raw_snarks = parse_snarks(config)
    if (len(raw_snarks) == 0):
      logging.warning("No messages were parsed.")
      sys.exit(1)

    snarks = process_snarks(config, raw_snarks)
    if (len(snarks) == 0):
      logging.warning("After processing, no messages were left.")
      sys.exit(1)

    logging.info("Calling %s exporter..." % config.exporter_name)
    export_snarks(config, snarks)

    logging.info("Done.")

  except (common.CompileSubsException) as err:
    # Parser or Exporter failed in an uninteresting way.
    logging.error(str(err))
    sys.exit(1)

  except (Exception) as err:
    logging.exception(err)
    sys.exit(1)


def parse_snarks(config):
  """Returns a list of raw snark dicts{user,msg,date} from a parser.

  :raises: ParserError
  """
  parsers_pkg = __import__("lib.parsers", globals(), locals(), [config.parser_name])
  parser_mod = getattr(parsers_pkg, config.parser_name)
  parse_func = getattr(parser_mod, "fetch_snarks")
  snarks = parse_func(config.src_path, config.first_msg, config.parser_options)

  return snarks


def process_snarks(config, snarks):
  """Adds info to, and temporally fudges, a list of raw snarks.
  While a snark's "date" is its original real-world datestamp,
  "time" is relative to the first snark's "date" and is subject
  to fudging.
  If enabled in config, "color" is an RGB float tuple (0.0-1.0),
  assigned randomly.

  :return: A list of processed snark dicts{user,msg,date,time,color}.
  """

  # Sort the msgs by their real-world date.
  snarks[:] = sorted(snarks, key=lambda k: k["date"])

  # Add in-movie time info to them.
  for snark in snarks:
    snark["time"] = snark["date"] - snarks[0]["date"] + config.fudge_time

    # Search backward through a user's delays for one in the recent past.
    if (snark["user"] in config.fudge_users):
      for (bookmark, fudge_value) in reversed(config.fudge_users[snark["user"]]):
        if (snark["time"] > bookmark):
          snark["time"] += fudge_value
          break

  # Omit snarks that got shifted into negative times.
  snarks[:] = [x for x in snarks if (abs(x["time"]) == x["time"])]

  # Omit snarks beyond the end time, if set.
  if (config.end_time is not None):
    snarks[:] = [x for x in snarks if (x["time"] <= config.end_time)]

  # Sort the msgs by their in-movie time.
  snarks[:] = sorted(snarks, key=lambda k: k["time"])

  # Assign unique colors, and paint each snark.
  if (config.color_enabled == "random"):
    unique_users = set(x["user"] for x in snarks)
    unique_colors = get_random_colors(len(unique_users))
    #write_palette_preview("./preview.html", unique_colors)

    color_users = dict(zip(unique_users, unique_colors))
    for snark in snarks:
      snark["color"] = color_users[snark["user"]]
  elif (config.color_enabled == "no"):
    for snark in snarks:
      if ("color" in snark): del snark["color"]

  return snarks


def export_snarks(config, snarks):
  """Sends a list of processed snark dicts to an exporter.

  :raises: ExporterError
  """
  exporters_pkg = __import__("lib.exporters", globals(), locals(), [config.exporter_name])
  exporter_mod = getattr(exporters_pkg, config.exporter_name)
  write_func = getattr(exporter_mod, "write_snarks")
  needs_file = getattr(exporter_mod, "needs_file")

  if (config.dest_path and needs_file):
    # Give the exporter a file-like object.
    with open(config.dest_path, 'wb') as dest_file:
      write_func(dest_file, snarks, config.show_time, config.exporter_options)
  else:
    # An empty string or None!? Maybe the exporter doesn't write.
    write_func(None, snarks, config.show_time, config.exporter_options)


def get_random_colors(count):
  """Gets a list of arbitrary colors.
   I had a fancy HSV randomizer with the colorsys module,
   but it was hit and miss. So now there's a prefab list.
     http://jsfiddle.net/k8NC2/1/
     http://stackoverflow.com/questions/470690/how-to-automatically-generate-n-distinct-colors

  :param count: The number of colors needed (too many, and you'll get white).
  :return: A list of RGB float tuples (0.0-1.0).
  """
  color_library = [("white", "FFFFFF"),
                   ("kelly-vivid-yellow", "FFB300"),
                   ("kelly-strong-purple", "803E75"),
                   #("kelly-vivid-orange", "FF6800"),
                   ("kelly-very-light-blue", "A6BDD7"),
                   ("kelly-vivid-red", "C10020"),
                   ("kelly-grayish-yellow", "CEA262"),
                   #("kelly-medium-gray", "817066"),
                   ("kelly-vivid-green", "007D34"),
                   #("kelly-strong-purplish-pink", "F6768E"),
                   ("kelly-strong-blue", "00538A"),
                   #("kelly-strong-yellowish-pink", "FF7A5C"),
                   ("kelly-strong-violet", "53377A"),
                   #("kelly-vivid-orange-yellow", "FF8E00"),
                   #("kelly-strong-purplish-red", "B32851"),
                   #("kelly-vivid-greenish-yellow", "F4C800"),
                   ("kelly-strong-reddish-brown", "7F180D"),
                   #("kelly-vivid-yellowish-green", "93AA00"),
                   ("kelly-deep-yellowish-brown", "593315"),
                   #("kelly-reddish-orange", "F13A13"),
                   ##("kelly-dark-olive-green", "232C16"),
                   #("boynton-blue", "0000FF"),
                   #("boynton-red", "FF0000"),
                   ("boynton-green", "00FF00"),
                   ("boynton-yellow", "FFFF00"),
                   ("boynton-magenta", "FF00FF"),
                   ("boynton-pink", "FF8080"),
                   ("boynton-gray", "808080"),
                   #("boynton-brown", "800000"),
                   ("boynton-orange", "FF8000")
                   ]
  random.shuffle(color_library)
  if (count > len(color_library)):
    color_library.extend([("white","FFFFFF")] * (count - len(color_library)))

  result = [common.hex_to_rgb(y) for (x,y) in color_library[:count]]

  return result


def write_palette_preview(path, unique_colors):
  """Dumps colors to a sanity-preserving html file for eyeballing.
  A relic from debugging random palettes.

  :param path: A file path to write to.
  :param unique_colors: A list of RGB float tuples.
  """
  out_file = open(path, 'w')
  out_file.write("<html><body>\n");
  for color in unique_colors:
    out_file.write("<font color=\"#%s\"><b>#########</b></font><br />\n" % (common.rgb_to_hex(color)));
  out_file.write("</body></html>");
  out_file.close()



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

  logfile_handler = logging.FileHandler("log.txt", mode="w")
  logger.addHandler(logfile_handler)
  logfile_formatter = logging.Formatter("%(asctime)s %(levelname)s (%(module)s): %(message)s", "%Y-%m-%d %H:%M:%S")
  logfile_handler.setFormatter(logfile_formatter)

  main()
