from datetime import datetime, timedelta
import contextlib
import logging
import re
import sys
import urllib2

from lib import common


# Namespace for options.
ns = "stub."


def fetch_snarks(src_path, first_msg, options={}):
  """Collects snarks from somewhere.

  :param src_path: A url, or file.
  :param first_msg: If not None, ignore messages until this substring is found.
  :param options: A dict of extra options specific to this parser.
                  Not used.
  :return: A List of snark dicts.
  """
  snarks = []

  # These are the snark attributes expected from parsers.
  snark = {}
  snark["user"] = "@Someone"
  snark["msg"] = "Some human-readable ascii."
  snark["date"] = datetime(2011, 10, 31, 22, 55, 35)
  snarks.append(snark)

  return snarks
