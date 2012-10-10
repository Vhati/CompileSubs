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


# Namespace for config options.
ns = "stub."

# Names of lib.subsystem modules that should be set up in advance.
required_subsystems = []


def get_description():
  return "Collects snarks from somewhere."

def get_arginfo():
  args = []
  return args

def fetch_snarks(src_path, first_msg, options={}, keep_alive_func=None, sleep_func=None):
  """Collects snarks from somewhere.

  :param src_path: A url, or file.
  :param first_msg: If not None, ignore messages until this substring is found.
  :param options: A dict of extra options specific to this parser.
                  Not used.
  :param keep_alive_func: Optional replacement to get an abort boolean.
  :param sleep_func: Optional replacement to sleep N seconds.
  :return: A List of snark dicts.
  """
  if (keep_alive_func is None): keep_alive_func = global_config.keeping_alive
  if (sleep_func is None): sleep_func = global_config.nap

  snarks = []

  # These are the snark attributes expected from parsers.
  snark = {}
  snark["user"] = "@Someone"
  snark["msg"] = "Some human-readable ascii."
  snark["date"] = datetime(2011, 10, 31, 22, 55, 35)
  snarks.append(snark)

  return snarks
