from datetime import datetime, timedelta
import logging
import pickle
import re
import sys

from lib import arginfo
from lib import common


# Namespace for options.
ns = "pickled_snarks."

# Whether dest_file arg is used.
uses_dest_file = True


def get_description():
  return "Writes snarks to a pickle file."

def get_arginfo():
  args = []
  return args

def write_snarks(dest_file, snarks, show_time, options={}):
  """Writes snarks to a pickle file.

  This will save EVERY attribute of snarks, in case a
  parser adds non-standard ones.

  :param dest_file: A binary-mode file-like object to write into.
  :param snarks: A list of processed snark dicts.
  :param show_time: Timedelta duration each msg appears on-screen.
  :param options: A dict of extra options specific to this exporter.
                  Not used.
  """
  pickle.dump(snarks, dest_file)
