from datetime import datetime, timedelta
import cgi
import logging
import re
import sys
import time
import urllib2

from lib import arginfo
from lib import common
from lib import global_config


# Namespace for options.
ns = "transcript_html."

# Whether dest_file arg is used.
uses_dest_file = True

# Names of lib.subsystem modules that should be set up in advance.
required_subsystems = []


def get_description():
  return "Writes snarks as html with links to each user and comment."

def get_arginfo():
  args = []
  args.append(arginfo.Arg(name="excerpt_only", type=arginfo.BOOLEAN,
              required=False, default=True, choices=[True,False], multiple=False,
              description="Boolean to only generate an excerpt to paste elsewhere.\nDefault is True."))
  args.append(arginfo.Arg(name="faux_twitter_links", type=arginfo.BOOLEAN,
              required=False, default=False, choices=[True,False], multiple=False,
              description="Boolean to guess twitter user links, if the parser didn't provide them.\nLinks to comments still can't be guessed and will be \"#\"\nDefault is False."))
  return args

def write_snarks(dest_file, snarks, show_time, options={}, keep_alive_func=None, sleep_func=None):
  """Writes snarks as html with links to each user and comment.

  Links will be inert unless snarks have the non-standard
  "user_url" and "msg_url" attributes, or the faux_twitter_links
  option is set.

  :param dest_file: A binary-mode file-like object to write into.
  :param snarks: A list of processed snark dicts.
  :param show_time: Timedelta duration each msg appears on-screen.
  :param options: A dict of extra options specific to this exporter.
                  excerpt_only (optional):
                      Boolean to only generate an excerpt to paste
                      elsewhere. Default is True.
                  faux_twitter_links (optional):
                      Boolean to guess twitter user links, if snarks
                      lack the "user_url" attribute. But links to
                      comments will still be "#". Default is False.
  :param keep_alive_func: Optional replacement to get an abort boolean.
  :param sleep_func: Optional replacement to sleep N seconds.
  """
  if (keep_alive_func is None): keep_alive_func = global_config.keeping_alive
  if (sleep_func is None): sleep_func = global_config.nap

  if (ns+"excerpt_only" in options and options[ns+"excerpt_only"] is False):
    dest_file.write("<html>\r\n<body>\r\n")

  for snark in snarks:
    snark_user_url = "#"
    if ("user_url" in snark):
      snark_user_url = snark["user_url"]
    elif (ns+"faux_twitter_links" in options and ns+"faux_twitter_links"):
      snark_user_url = "http://www.twitter.com/%s" % urllib2.quote(re.sub("^@", "", snark["user"]))

    snark_msg_url = "#"
    if ("msg_url" in snark):
      snark_msg_url = snark["msg_url"]
    elif (ns+"faux_twitter_links" in options and ns+"faux_twitter_links"):
      pass

    snark_date = snark["date"].strftime("%Y-%m-%d %H:%M:%S")

    # User names will always have @.
    snark_user = re.sub("^[^@]", "@&", snark["user"])

    snark_msg = snark["msg"]
    snark_msg = cgi.escape(snark_msg)  # Escape [<>&]

    # Represent newlines with <br/>.
    snark_msg = re.sub("\n", "<br/>", snark_msg)

    # Numerically escape exotic chars.
    badchar_ptn = re.compile(eval(r'u"[\u0080-\uffff]"'))  # Removed &<>\" from [] brackets.

    snark_msg = re.sub(badchar_ptn, lambda m: ("&#%d;" % ord(m.group(0))), snark_msg)

    dest_file.write("<a href='%s'>%s</a>: %s <br/><font size=-3><a href='%s' style='color: grey; text-decoration: none;'>%s</a></font><br/>" % (snark_user_url, snark_user, snark_msg, snark_msg_url, snark_date))
    dest_file.write("\r\n")

  if (ns+"excerpt_only" in options and options[ns+"excerpt_only"] is False):
    dest_file.write("</body>\r\n</html>\r\n")
