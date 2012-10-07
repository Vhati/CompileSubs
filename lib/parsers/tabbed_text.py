from datetime import datetime, timedelta
import contextlib
import logging
import re
import sys
import urllib2

from lib import arginfo
from lib import common


# Namespace for options.
ns = "tabbed_text."


def get_description():
  return "Collects snarks from tab-separated text."

def get_arginfo():
  args = []
  args.append(arginfo.Arg(name="reply_name", type=arginfo.STRING,
              required=False, default=None, choices=None, multiple=False,
              description="The name to which replies were directed (no \"@\").\nRegexes will remove it from messages."))
  return args

def fetch_snarks(src_path, first_msg, options={}):
  """Collects snarks from tab-separated text.

  Columns: In-Movie Time, Original Date, Color, User, Msg.
  The "time" column is ignored, and "color" might be
  clobbered later.

  :param src_path: A url, or file.
  :param first_msg: If not None, ignore messages until this substring is found.
  :param options: A dict of extra options specific to this parser.
                  reply_name (optional):
                      The name to which replies were directed (no "@").
                      Regexes will remove it from messages.
  :return: A List of snark dicts.
  :raises: ParserError
  """
  snark_ptn = re.compile("[^t]*\t([0-9]{4})-([0-9]{2})-([0-9]{2}) ([0-9]{2}):([0-9]{2}):([0-9]{2})\t([0-9A-Fa-f]{6}?)\t([^\t]+)\t([^\t]+)")

  # List of pattern/replacement tuples to strip reply topic from messages.
  reply_regexes = []
  if (ns+"reply_name" in options and options[ns+"reply_name"]):
    reply_name_escaped = re.escape(options[ns+"reply_name"])
    reply_regexes = [(re.compile(" +@"+ reply_name_escaped +" +", re.IGNORECASE), " "),
                     (re.compile(" *@"+ reply_name_escaped +" *", re.IGNORECASE), "")]

  start_date = None
  snarks = []

  lines = []
  try:
    with contextlib.closing(urllib2.urlopen(src_path)) as snark_file:
      while (True):
        line = snark_file.readline()
        if (line == ''): break
        line = re.sub("\r\n?", "\n", line)  # Local files are opened without universal newlines.
        line = line[:-1]
        lines.append(line)
  except (urllib2.HTTPError) as err:
    logging.error("Http status: %d" % err.code)
    raise common.ParserError("Parser failed.")
  except (urllib2.URLError) as err:
    logging.error(str(err))
    raise common.ParserError("Parser failed.")

  for line in lines:
    result = snark_ptn.match(line)
    if (result is None):
      if (line != lines[0]): logging.warning("Bad line: %s" % line)
      continue

    snark = {}
    snark["user"] = result.group(8)
    snark["msg"] = result.group(9)
    snark["msg"] = snark["msg"].replace("\\n", "\n")
    for reply_ptn, reply_rep in reply_regexes:
      snark["msg"] =  reply_ptn.sub(reply_rep, snark["msg"])

    year, month, day = [int(result.group(i)) for i in [1,2,3]]
    hour, minute, second = [int(result.group(i)) for i in [4,5,6]]

    snark["date"] = datetime(year, month, day, hour, minute, second)

    if (result.group(7)):
      snark["color"] = common.hex_to_rgb(result.group(7))

    if (start_date is None):
      if (first_msg and line.find(first_msg) == -1):
        # This snark was earlier than the expected first msg.
        continue
      start_date = snark["date"]

    snarks.append(snark)

  return snarks
