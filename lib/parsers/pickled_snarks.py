from datetime import datetime, timedelta
import logging
import pickle
import re
import sys
import time
import urlparse

from lib import arginfo
from lib import common
from lib import global_config


# Namespace for options.
ns = "pickled_snarks."

# Names of lib.subsystem modules that should be set up in advance.
required_subsystems = []


def get_description():
  return "Collects snarks from a pickle file."

def get_arginfo():
  args = []
  return args

def fetch_snarks(src_path, first_msg, options={}, keep_alive_func=None, sleep_func=None):
  """Collects snarks from a pickle file.

  This will restore EVERY attribute of saved snarks.
  The "time" and "color" attributes may still be
  clobbered later, however.

  :param src_path: A local file (because other urls aren't read as binary).
  :param first_msg: If not None, ignore messages until this substring is found.
  :param options: A dict of extra options specific to this parser.
                  Not used.
  :param keep_alive_func: Optional replacement to get an abort boolean.
  :param sleep_func: Optional replacement to sleep N seconds.
  :return: A List of snark dicts.
  :raises: ParserError
  """
  if (keep_alive_func is None): keep_alive_func = global_config.keeping_alive
  if (sleep_func is None): sleep_func = global_config.nap

  if (not src_path): raise common.ParserError("The %s parser requires the general arg, \"src_path\", to be set." % re.sub(".*[.]", "", __name__))

  start_date = None
  snarks = []

  pickled_snarks = []
  try:
    p = urlparse.urlparse(src_path)
    if (p.scheme != "file"):
      logging.error("This parser only supports \"file:\" urls.")
      raise common.ParserError("Parser failed.")

    src_path = "".join([p.netloc, p.path])
    with open(src_path, "rb") as snark_file:
      pickled_snarks = pickle.load(snark_file)
  except (IOError) as err:
    logging.error(str(err))
    raise common.ParserError("Parser failed.")

  for snark in pickled_snarks:
    if (start_date is None):
      if (first_msg and snark["msg"].find(first_msg) == -1):
        # This snark was earlier than the expected first msg.
        continue
      start_date = snark["date"]

    snarks.append(snark)

  return snarks
