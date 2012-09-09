from datetime import datetime, timedelta
import logging
import re
import sys

from lib import common


# Namespace for options.
ns = "tabbed_text."

# Whether dest_file arg is used.
needs_file = True


def write_snarks(dest_file, snarks, show_time, options={}):
  """Writes snarks as tab-separated text.

  Columns: In-Movie Time, Original Date, Color, User, Msg.

  Newlines in "msg" are represented with \n.

  :param dest_file: A binary-mode file-like object to write into.
  :param snarks: A list of processed snark dicts.
  :param show_time: Timedelta duration each msg appears on-screen.
  :param options: A dict of extra options specific to this exporter.
                  Not used.
  """
  dest_file.write("\t".join(["In-Movie Time", "Original Date", "Color", "User", "Msg"]))
  dest_file.write("\r\n")

  for snark in snarks:
    snark_start = common.delta_str(snark["time"])
    snark_date = snark["date"].strftime("%Y-%m-%d %H:%M:%S")

    snark_color = ""
    if ("color" in snark and snark["color"] is not None):
      snark_color = common.rgb_to_hex(snark["color"])

    # Represent newlines with \n.
    snark_msg = snark["msg"].replace("\n", "\\n")

    dest_file.write("\t".join([snark_start, snark_date, snark_color, snark["user"], snark_msg]))
    dest_file.write("\r\n")
