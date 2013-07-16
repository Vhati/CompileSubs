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
from lib import global_config
from lib.subsystems import tweepy_backend


# Namespace for options.
ns = "twitter_search."

# Names of lib.subsystem modules that should be set up in advance.
required_subsystems = ["tweepy_backend"]


def get_description():
  return ("Collects snarks from a Twitter search.\n"+
          "Finds tweets from any account and @reply mentions of it.\n\n"+
          "Note: Twitter's search API only reaches back a few days "+
          "and may be incomplete.\n"+
          "On first use, it will prompt for authorization.")

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
  return args

def fetch_snarks(src_path, first_msg, options={}, keep_alive_func=None, sleep_func=None):
  """Collects snarks from a Twitter search. Finds
  tweets from any account and @reply mentions of it.
  See: https://dev.twitter.com/docs/api/1/get/search

  This parser adds non-standard attributes to snarks:
  "user_url" and "msg_url", links to the user's twitter
  page and to the specific tweet. Exporters might
  disregard this info.

  Twitter's search API only reaches back a few days
  and may be incomplete. :/

  :param src_path: Not used.
  :param first_msg: If not None, ignore comments prior to one containing this substring.
  :param options: A dict of extra options specific to this parser.
                  reply_name:
                      The name to which replies were directed (no "@").
                  since_date (optional):
                      UTC Datetime to limit dredging up old tweets.
                  until_date (optional):
                      UTC Datetime to limit dredging up new tweets.
  :param keep_alive_func: Optional replacement to get an abort boolean.
  :param sleep_func: Optional replacement to sleep N seconds.
  :return: A List of snark dicts.
  :raises: ParserError
  """
  if (keep_alive_func is None): keep_alive_func = global_config.keeping_alive
  if (sleep_func is None): sleep_func = global_config.nap

  since_date = None
  if (ns+"since_date" in options and options[ns+"since_date"]):
    since_date = options[ns+"since_date"]

  until_date = None
  if (ns+"until_date" in options and options[ns+"until_date"]):
    until_date = options[ns+"until_date"]

  missing_options = [o for o in ["reply_name"] if ((ns+o) not in options or not options[ns+o])]
  if (len(missing_options) > 0):
    logging.error("Required parser options weren't provided: %s." % ", ".join(missing_options))
    raise common.ParserError("Parser failed.")

  snarks = []

  tweepy = tweepy_backend.get_tweepy()
  tweepy_api = tweepy_backend.get_api()

  try:
    # List of pattern/replacement tuples to strip reply topic from comments.
    reply_name_escaped = re.escape(options[ns+"reply_name"])
    reply_regexes = [(re.compile(" +@"+ reply_name_escaped +" +", re.IGNORECASE), " "),
                     (re.compile(" *@"+ reply_name_escaped +" *", re.IGNORECASE), "")]

    search_args = {"rpp":100, "include_entities":"false", "result_type":"recent"}
    search_args["q"] = "@%s OR from:%s" % (options[ns+"reply_name"], options[ns+"reply_name"])
    if (since_date): search_args["since"] = since_date.strftime("%Y-%m-%d")
    if (until_date): search_args["until"] = until_date.strftime("%Y-%m-%d")
    search_rate = {"reset":None, "limit":0, "remaining":0, "res_family":"search", "res_name":"/search/tweets"}

    searches = []
    searches.append(("Search", tweepy_api.search, search_args, 1500, search_rate))

    def update_rate_info():
      # Sets new rate info values for the searches.
      rate_status = tweepy_api.rate_limit_status()
      for (search_type, tweepy_func, tweepy_func_args, search_cap, rate_info) in searches:
        rate_info.update(rate_status["resources"][rate_info["res_family"]][rate_info["res_name"]])

    update_rate_info()

    for (search_type, tweepy_func, tweepy_func_args, search_cap, rate_info) in searches:
      done = False
      query_count = 0
      results_count = 0
      last_max_id = None

      while (keep_alive_func() and done is False and results_count < search_cap and rate_info["remaining"] > 0):
        results = tweepy_func(**tweepy_func_args)
        rate_info["remaining"] -= 1
        if (not results):
          done = True
          break
        else:
          query_count += 1
          results_count += len(results)
          logging.info("%s Query % 2d: % 3d results." % (search_type, query_count, len(results)))

          last_id = None
          for search_result in results:
            if (last_max_id == search_result.id): continue
            last_id = search_result.id

            snark = {}
            snark["user"] = "@%s" % common.asciify(search_result.from_user)
            snark["msg"] = search_result.text
            for (reply_ptn, reply_rep) in reply_regexes:
              snark["msg"] =  reply_ptn.sub(reply_rep, snark["msg"])
            snark["msg"] = common.asciify(common.html_unescape(snark["msg"]))

            snark["date"] = search_result.created_at

            snark["user_url"] = "http://www.twitter.com/%s" % common.asciify(search_result.from_user)
            snark["msg_url"] = "http://twitter.com/#!/%s/status/%d" % (common.asciify(search_result.from_user), search_result.id)

            if (until_date and snark["date"] > until_date):
              continue  # This snark is too recent.

            if (since_date and snark["date"] < since_date):
              done = True  # This snark is too early.
              break

            snarks.append(snark)

            if (first_msg):
              if (snark["msg"].find(first_msg) != -1):
                done = True  # Found the first comment.
                break

          if (last_id is not None):
            # Dig deeper into the past on the next loop.
            tweepy_func_args["max_id"] = last_id
            last_max_id = last_id
          else:
            # Must've only gotten the "max_id" tweet again.
            done = True
            break

          if (rate_info["reset"] is not None and time.time() >= float(rate_info["reset"])):
            update_rate_info()

            reset_string = datetime.fromtimestamp(float(rate_info["reset"])).strftime("%Y-%m-%d %H:%M:%S")
            logging.info("API limit for '%s' reset. Calls left: %d (Until %s)" % (rate_info["res_name"], rate_info["remaining"], reset_string))

      if (done is False and rate_info["remaining"] <= 0):
        logging.warning("Twitter API rate limit truncated results for '%s'." % rate_info["res_name"])
        break  # No more searches.

    update_rate_info()
    logging.info("Twitter API calls left...")
    for (search_type, tweepy_func, tweepy_func_args, search_cap, rate_info) in searches:
      reset_string = datetime.fromtimestamp(float(rate_info["reset"])).strftime("%Y-%m-%d %H:%M:%S")
      logging.info("'%s': %d (Until %s)." % (rate_info["res_name"], rate_info["remaining"], reset_string))
    logging.info("Current Time: %s" % datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

  except (Exception) as err:
    logging.exception("Parser failed.")
    raise common.ParserError("Parser failed.")

  snarks = sorted(snarks, key=lambda k: k["date"])

  # Drop duplicates from multiple passes.
  snarks = uniquify_list(snarks)

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
