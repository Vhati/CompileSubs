from datetime import datetime, timedelta
import logging
import re
import sys
import time

from lib import arginfo
from lib import common
from lib import global_config


# Namespace for options.
ns = "stub."

# Whether dest_file arg is used.
uses_dest_file = True

# Names of lib.subsystem modules that should be set up in advance.
required_subsystems = []


def get_description():
  return "Writes snarks to nowhere."

def get_arginfo():
  args = []
  return args

def write_snarks(dest_file, snarks, show_time, options={}, keep_alive_func=None, sleep_func=None):
  """Writes snarks to nowhere.

  :param dest_file: A binary-mode file-like object to write into.
  :param snarks: A list of processed snark dicts.
  :param show_time: Timedelta duration each msg appears on-screen.
  :param options: A dict of extra options specific to this exporter.
                  Not used.
  :param keep_alive_func: Optional replacement to get an abort boolean.
  :param sleep_func: Optional replacement to sleep N seconds.
  """
  if (keep_alive_func is None): keep_alive_func = global_config.keeping_alive
  if (sleep_func is None): sleep_func = global_config.nap

  pass
