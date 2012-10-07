from datetime import datetime, timedelta
import logging
import re
import sys

from lib import arginfo
from lib import common


# Namespace for options.
ns = "stub."

# Whether dest_file arg is used.
uses_dest_file = True


def get_description():
  return "Writes snarks to nowhere."

def get_arginfo():
  args = []
  return args

def write_snarks(dest_file, snarks, show_time, options={}):
  """Writes snarks to nowhere.

  :param dest_file: A binary-mode file-like object to write into.
  :param snarks: A list of processed snark dicts.
  :param show_time: Timedelta duration each msg appears on-screen.
  :param options: A dict of extra options specific to this exporter.
                  Not used.
  """
  pass
