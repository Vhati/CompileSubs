from datetime import datetime, timedelta
import contextlib
import logging
import re
import sys
import time
import urllib2

from lib import arginfo
from lib import common
from lib import global_config


# Namespace for options.
ns = "tweetsubs_log."

# Names of lib.subsystem modules that should be set up in advance.
required_subsystems = []


def get_description():
  return "Collects snarks from a TweetSubs log.\nSee: https://github.com/Vhati/TweetSubs"

def get_arginfo():
  args = []
  return args

def fetch_snarks(src_path, first_msg, options={}, keep_alive_func=None, sleep_func=None):
  """Collects snarks from a TweetSubs log.
  See: https://github.com/Vhati/TweetSubs

  :param src_path: A url, or file.
  :param first_msg: If not None, ignore comments until this substring is found.
  :param options: A dict of extra options specific to this parser.
                  Not used.
  :param keep_alive_func: Optional replacement to get an abort boolean.
  :param sleep_func: Optional replacement to sleep N seconds.
  :return: A List of snark dicts.
  :raises: ParserError
  """
  if (keep_alive_func is None): keep_alive_func = global_config.keeping_alive
  if (sleep_func is None): sleep_func = global_config.nap

  if (not src_path): raise common.ParserError("The %s parser requires the general arg, \"src_path\", to be set." % re.sub(".*[.]", "", __name__))

  snark_ptn = re.compile("([0-9]{4})-([0-9]{2})-([0-9]{2}) ([0-9]{2}):([0-9]{2}):([0-9]{2}) INFO: Tweet (?:shown|expired) [(]lag ([0-9-]+)s[)]: ([^:]+): (.*)")
  start_date = None
  snarks = []
  prev_line_was_snark = False

  lines = []
  try:
    with contextlib.closing(urllib2.urlopen(src_path)) as snark_file:
      while (keep_alive_func()):
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
      # Lines without a logging datestamp must be part of a multiline snark.
      if (len(snarks) > 0 and prev_line_was_snark is True and re.match("[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2} [^:]+: .*", line) is None):
        snarks[-1]["msg"] += "\n"+ line
        prev_line_was_snark = True
      else:
        prev_line_was_snark = False
      continue

    snark = {}
    snark["user"] = "@%s" % result.group(8)
    snark["msg"] =  result.group(9)

    year, month, day = [int(result.group(i)) for i in [1,2,3]]
    hour, minute, second = [int(result.group(i)) for i in [4,5,6]]
    lag_seconds = int(result.group(7))

    # Local time zone
    snark["date"] = datetime(year, month, day, hour, minute, second)
    snark["date"] = snark["date"] - timedelta(seconds=lag_seconds)

    if (start_date is None):
      if (first_msg and line.find(first_msg) == -1):
        # This snark was earlier than the expected first msg.
        continue
      start_date = snark["date"]

    snarks.append(snark)
    prev_line_was_snark = True

  return snarks
