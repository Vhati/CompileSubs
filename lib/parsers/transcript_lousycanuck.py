from datetime import datetime, timedelta
import contextlib
import logging
import re
import sys
import urllib2

from lib import common


# Namespace for options.
ns = "lousycanuck."


def fetch_snarks(src_path, first_msg, options={}):
  """Collects snarks from an html Transcript post on LousyCanuck's blog.
  See: http://twitter.com/MockTM
  See: http://freethoughtblogs.com/lousycanuck/

  :param src_path: A url, or saved html source.
  :param first_msg: If not None, ignore messages until this substring is found.
  :param options: A dict of extra options specific to this parser.
                  reply_name (optional):
                      The name to which replies were directed.
                      Regexes will remove it from messages.
  :return: A List of snark dicts.
  :raises: ParserError
  """
  # Regex to parse tweet info out of html.
  snark_ptn = re.compile("(?:<p>)?<a href='[^']*'>([^<]*)</a>: (.*?) +<br ?/><font size=-3><a href='[^']*'[^>]*>([0-9]{4})-([0-9]{2})-([0-9]{2}) ([0-9]{2}):([0-9]{2}):([0-9]{2})</a></font>(?:<br ?/>|</p>)?", re.IGNORECASE)

  # List of pattern/replacement tuples to strip reply topic from messages.
  reply_regexes = []
  if (ns+"reply_name" in options and options[ns+"reply_name"]):
    reply_name_escaped = re.escape(options[ns+"reply_name"])
    reply_regexes = [(re.compile(" +@"+ reply_name_escaped +" +", re.IGNORECASE), " "),
                     (re.compile(" *@"+ reply_name_escaped +" *", re.IGNORECASE), "")]

  # Regex to know when to stop parsing.
  tail_ptn = re.compile("<div class=\"[^\"]*robots-nocontent[^\"]*\">")

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
    if (tail_ptn.search(line) is not None): break

    result = snark_ptn.match(line)
    if (result is None):
      # Only complain once the first snark is found.
      if (start_date is not None): logging.warning("Bad Line: "+ line)
      continue

    snark = {}
    snark["user"] = result.group(1)
    snark["msg"] =  result.group(2)
    for reply_ptn, reply_rep in reply_regexes:
      snark["msg"] =  reply_ptn.sub(reply_rep, snark["msg"])
    snark["msg"] =  common.asciify(common.html_unescape(snark["msg"]))

    year, month, day = [int(result.group(i)) for i in [3,4,5]]
    hour, minute, second = [int(result.group(i)) for i in [6,7,8]]

    # UTC time zone?
    snark["date"] = datetime(year, month, day, hour, minute, second)

    if (start_date is None):
      if (first_msg is not None and line.find(first_msg) == -1):
        # This snark was earlier than the expected first msg.
        continue
      start_date = snark["date"]

    snarks.append(snark)

  return snarks
