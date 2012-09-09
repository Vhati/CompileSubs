from datetime import datetime, timedelta
import logging
import pickle
import re
import sys
import urlparse

from lib import common


# Namespace for options.
ns = "pickled_snarks."


def fetch_snarks(src_path, first_msg, options={}):
  """Collects snarks from a pickle file.

  This will restore EVERY attribute of saved snarks.
  The "time" and "color" attributes may still be
  clobbered later, however.

  :param src_path: A local file (because other urls aren't read as binary).
  :param first_msg: If not None, ignore messages until this substring is found.
  :param options: A dict of extra options specific to this parser.
                  Not used.
  :return: A List of snark dicts.
  :raises: ParserError
  """
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
      if (first_msg is not None and snark["msg"].find(first_msg) == -1):
        # This snark was earlier than the expected first msg.
        continue
      start_date = snark["date"]

    snarks.append(snark)

  return snarks
