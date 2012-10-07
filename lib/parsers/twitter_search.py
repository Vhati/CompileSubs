from datetime import datetime, timedelta
import contextlib
import json
import logging
import re
import sys
import time
import urllib2

from lib import arginfo
from lib import common


# Namespace for options.
ns = "twitter_search."


def get_description():
  return ("Collects snarks from a Twitter search.\n"+
          "Finds tweets from an account and any @reply mentions of it.")

def get_arginfo():
  args = []
  args.append(arginfo.Arg(name="reply_name", type=arginfo.STRING,
              required=True, default=None, choices=None, multiple=False,
              description="The name to which replies were directed (no \"@\")."))
  args.append(arginfo.Arg(name="since_date", type=arginfo.DATETIME,
              required=False, default=None, choices=None, multiple=False,
              description="UTC date to limit dredging up old tweets."))
  args.append(arginfo.Arg(name="until_date", type=arginfo.DATETIME,
              required=False, default=None, choices=None, multiple=False,
              description="UTC date to limit dredging up new tweets."))
  args.append(arginfo.Arg(name="passes", type=arginfo.INTEGER,
              required=False, default=1, choices=None, multiple=False,
              description="Search X times to fill omissions in results."))
  return args

def fetch_snarks(src_path, first_msg, options={}):
  """Collects snarks from a Twitter search. Finds
  tweets from an account and any @reply mentions of it.
  See: https://dev.twitter.com/docs/api/1/get/search

  This parser adds non-standard attributes to snarks:
  "user_url" and "msg_url", links to the user's twitter
  page and to the specific tweet. Exporters might
  disregard this info.

  Any given search may be incomplete, but this parser can
  make multiple passes to mitigate that. It's recommended
  that you initially search and export to a temporary
  pickled_snarks file; then parse THAT repeatedly to apply
  adjustments and export to the final desired format.

  Twitter's search API only reaches back a few days. :/

  :param src_path: Not used.
  :param first_msg: If not None, ignore messages prior to one containing this substring.
  :param options: A dict of extra options specific to this parser.
                  reply_name:
                      The name to which replies were directed (no "@").
                  since_date (optional):
                      UTC Datetime to limit dredging up old tweets.
                  until_date (optional):
                      UTC Datetime to limit dredging up new tweets.
                  passes (optional):
                      Search X times to fill omissions in results.
  :return: A List of snark dicts.
  :raises: ParserError
  """
  search_url = "http://search.twitter.com/search.json"

  since_date = None
  if (ns+"since_date" in options and options[ns+"since_date"]):
    since_date = options[ns+"since_date"]

  until_date = None
  if (ns+"until_date" in options and options[ns+"until_date"]):
    until_date = options[ns+"until_date"]

  passes_remaining = 0
  if (ns+"passes" in options and options[ns+"passes"] > 1):
    passes_remaining = options[ns+"passes"] - 1

  missing_options = [o for o in ["reply_name"] if ((ns+o) not in options or not options[ns+o])]
  if (len(missing_options) > 0):
    logging.error("Required parser options weren't provided: %s." % ", ".join(missing_options))
    raise common.ParserError("Parser failed.")

  # List of pattern/replacement tuples to strip reply topic from messages.
  reply_name_escaped = re.escape(options[ns+"reply_name"])
  reply_regexes = [(re.compile(" +@"+ reply_name_escaped +" +", re.IGNORECASE), " "),
                   (re.compile(" *@"+ reply_name_escaped +" *", re.IGNORECASE), "")]

  query = urllib2.quote("@%s OR from:%s" % (options[ns+"reply_name"], options[ns+"reply_name"]))
  if (since_date): query += urllib2.quote(" since:%s" % since_date.strftime("%Y-%m-%d"))
  if (until_date): query += urllib2.quote(" until:%s" % until_date.strftime("%Y-%m-%d"))
  original_url = "%s?q=%s&rpp=100&page=1&result_type=recent" % (search_url, query)
  url = original_url
  logging.debug("Url: %s" % url)

  snarks = []
  pass_result_count = 0

  while (url is not None):
    notice_url = re.sub("[^?]+/search.json.*[?&](page=[0-9]+).*", "\g<1>", url)
    logging.info("Parsing: %s" % notice_url)
    time.sleep(1)

    json_obj = None
    try:
      with contextlib.closing(urllib2.urlopen(url)) as server_response:
        json_obj = json.loads(server_response.read())
    except (urllib2.HTTPError) as err:
      logging.error("Http status: %d" % err.code)
      raise common.ParserError("Parser failed.")
    except (urllib2.URLError) as err:
      logging.error(str(err))
      raise common.ParserError("Parser failed.")

    if (not json_obj or "results" not in json_obj):
      logging.error("Failed to parse search results.")
      raise common.ParserError("Parser failed.")

    pass_result_count += len(json_obj["results"])
    for result in json_obj["results"]:
      snark = {}
      snark["user"] = "@%s" % result["from_user"]
      snark["msg"] =  result["text"]
      for reply_ptn, reply_rep in reply_regexes:
        snark["msg"] =  reply_ptn.sub(reply_rep, snark["msg"])
      snark["msg"] =  common.asciify(common.html_unescape(snark["msg"]))

      snark["date"] = datetime.strptime(result["created_at"] +" UTC", '%a, %d %b %Y %H:%M:%S +0000 %Z')

      snark["user_url"] = "http://www.twitter.com/%s" % result["from_user"]
      snark["msg_url"] = "http://twitter.com/#!/%s/status/%s" % (result["from_user"], result["id"])

      snarks.append(snark)

    if ("next_page" in json_obj):
      url = search_url + json_obj["next_page"]
    elif (passes_remaining > 0):
      logging.info("Pass complete: %d results." % pass_result_count)
      passes_remaining -= 1
      url = original_url
      pass_result_count = 0
    else:
      url = None

  snarks = sorted(snarks, key=lambda k: k["date"])

  # Drop duplicates from multiple passes.
  snarks = uniquify_list(snarks)

  logging.info("Search complete: %d combined results." % len(snarks))

  if (first_msg):
    first_index = -1
    for i in range(len(snarks)):
      if (snarks[i]["msg"].find(first_msg) != -1):
        # Finally reached the expected first msg.
        first_index = i
    if (first_index >= 0):
      snarks = snarks[first_index:]
    else:
      logging.warning("first_msg string \"%s\" was not found." % first_msg)
      snarks = []

  return snarks


def uniquify_list(seq):
  seen = set()
  seen_add = seen.add
  return [x for x in seq if repr(x) not in seen and not seen_add( repr(x) )]
