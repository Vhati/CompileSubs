from datetime import datetime, timedelta
import logging
import os
import sys
import ConfigParser
import threading

from lib import tweepy

from lib import common
from lib import global_config


CONSUMER_KEY = "U1U08r2RLsfhxv3aqmncWQ"
CONSUMER_SECRET = "PxR6FTuo3bckt6BEbLUzdEyDtbyrikLatKGBuFfiM90"
tweepy_config_name = "tweepy.cfg"

tweepy_api = None
api_lock = threading.RLock()  # Singleton.


def init(keep_alive_func=None, sleep_func=None):
  """Performs initial setup.
  Subsequent calls after the first success are
  automatically successful.

  :param keep_alive_func: Optional replacement to get an abort boolean.
  :param sleep_func: Optional replacement to sleep N seconds.
  :returns: True if succesful, False otherwise.
  """
  global tweepy_api  # This variable might get modified.

  with api_lock:
    if (tweepy_api is None):
      if (keep_alive_func is None): keep_alive_func = global_config.keeping_alive
      if (sleep_func is None): sleep_func = global_config.nap

      tweepy_config_path = os.path.join(global_config.get_settings_dir(), tweepy_config_name)
      tweepy_auth = tweepy.OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
      try:
        tweepy_config = ConfigParser.RawConfigParser()
        tweepy_config.read(tweepy_config_path)
        if (tweepy_config.has_section("Credentials")):
          k = tweepy_config.get("Credentials", "access_key")
          s = tweepy_config.get("Credentials", "access_secret")
          if (k and s):
            tweepy_auth.set_access_token(k, s)

      except (Exception) as err:
        logging.error("Could not parse %s: %s" % (tweepy_config_path, str(err)))

      try:
        if (tweepy_auth.access_token is None):
          logging.info("Getting authorization url...")
          auth_url = tweepy_auth.get_authorization_url()

          notice = ("You need to authorize this application\n" +
                    "to interact with Twitter on your behalf.")
          verifier_string = common.prompt("PIN: ", notice=notice, url=auth_url)

          if (not verifier_string): raise tweepy.TweepError("No PIN was provided.")

          logging.info("Using PIN to fetch an access token.")
          tweepy_auth.get_access_token(verifier_string)

        temp_api = tweepy.API(tweepy_auth)
        if (temp_api.verify_credentials()):
          tweepy_api = temp_api

        try:
          tweepy_config = ConfigParser.RawConfigParser()
          tweepy_config.add_section("Credentials")
          tweepy_config.set("Credentials", "access_key", tweepy_auth.access_token.key)
          tweepy_config.set("Credentials", "access_secret", tweepy_auth.access_token.secret)
          with open(tweepy_config_path, "wb") as f: tweepy_config.write(f)

        except (Exception) as err:
          logging.error("Could not write %s: %s" % (tweepy_config_path, str(err)))

      except (tweepy.TweepError) as err:
        logging.error(str(err.reason))

    return is_ready()


def is_ready():
  """Returns True if init() has succeeded, False otherwise."""
  with api_lock:
    return (tweepy_api is not None)


def get_tweepy():
  """Get the tweepy module."""
  return tweepy


def get_api():
  """Get the tweepi api object.
  If init() has not yet succeeded, this will be None.
  """
  with api_lock:
    return tweepy_api


def rate_limit_status():
  """Requests rate limit info.
  This a convenience function that returns the standard dict,
  as well as an extra dict containing some of that info
  parsed into more useful forms.

  The format used to create date strings is included, too.

  {remaining_hits (int), hourly_limit (int),
   reset_time (UTC datetime), reset_time_string (string),
   new_date_format (string)}

  If Twitter changes their date format to break things, the
  reset datetime will be None, and the reset string will be
  the unaltered string Twitter returned.

  :returns: (rate_status, rate_parsed).
  """
  temp_api = get_api()
  rate_status = temp_api.rate_limit_status()

  rate_parsed = {}
  rate_parsed["remaining_hits"] = int(rate_status['remaining_hits'])
  rate_parsed["hourly_limit"] = int(rate_status["hourly_limit"])
  rate_parsed["reset_time"] = None
  rate_parsed["reset_time_string"] = rate_status["reset_time"]
  rate_parsed["new_date_format"] = "%Y-%m-%d %H:%M:%S"
  try:
    rate_parsed["reset_time"] = datetime.strptime(rate_status["reset_time"] +" UTC", "%a %b %d %H:%M:%S +0000 %Y %Z")
    rate_parsed["reset_time_string"] = rate_parsed["reset_time"].strftime(rate_parsed["new_date_format"]) +" UTC"

  except (Exception) as err:
    logging.debug("Failed to parse rate limit reset date (%s): %s." % (rate_status["reset_time"], str(err)))

  return (rate_status, rate_parsed)
