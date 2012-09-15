from datetime import datetime, timedelta
import logging
import re
import sys

from lib import common


# Namespace for options.
ns = "subrip."

# Whether dest_file arg is used.
needs_file = True


def write_snarks(dest_file, snarks, show_time, options={}):
  """Writes snarks as SubRip subtitles.

  :param dest_file: A binary-mode file-like object to write into.
  :param snarks: A list of processed snark dicts.
  :param show_time: Timedelta duration each msg appears on-screen.
  :param options: A dict of extra options specific to this exporter.
                  include_names (optional):
                      Boolean to prepend snark each msg with user.
                      Default is True.
  """
  include_names = True
  if (ns+"include_names" in options and not options[ns+"include_names"]):
    include_names = False

  srt_index = 0

  palette_start = srt_delta_str(timedelta(seconds=1))
  palette_end = srt_delta_str(timedelta(seconds=1) + show_time)
  palette_msg = ""

  unique_colors = list(set([x["color"] for x in snarks if ("color" in x)]))
  if (len(unique_colors) > 0):
    for c in unique_colors:
      palette_msg += color_message("#", c)

    if (len(palette_msg) > 0):
      srt_index += 1
      dest_file.write(str(srt_index) +"\r\n")
      dest_file.write(palette_start +" --> "+ palette_end +"\r\n")
      dest_file.write(palette_msg +"\r\n")
      dest_file.write("\r\n")

  for snark in snarks:
    srt_start = srt_delta_str(snark["time"])
    srt_end = srt_delta_str(snark["time"] + show_time)
    srt_msg = snark["msg"]

    if ("color" in snark and snark["color"] is not None):
      srt_msg = color_message(srt_msg, snark["color"])

    # SubRip tolerates multiple lines, but not blank lines.
    srt_msg = re.sub("\r", "", srt_msg)
    srt_msg = re.sub("\n\n+", "\n", srt_msg)

    # Remove empty space and links.
    srt_msg = re.sub("^ +", "", srt_msg)
    srt_msg = re.sub(" *\n *", "\n", srt_msg)
    srt_msg = srt_msg.rstrip(" \n")
    srt_msg = re.sub(" *https?://[^ ]+", "", srt_msg)

    if (include_names is True):
      srt_msg = "%s: %s" % (snark["user"].replace("@",""), srt_msg)

    srt_msg = re.sub("\n", "\r\n", srt_msg)  # Reintroduce CR's.

    srt_index += 1
    dest_file.write(str(srt_index) +"\r\n")
    dest_file.write(srt_start +" --> "+ srt_end +"\r\n")
    dest_file.write(srt_msg +"\r\n")
    dest_file.write("\r\n")


def srt_delta_str(delta):
  """Formats a timedelta as an srt string.
  A millisecond suffix is appended to make
  SubRip happy.

  :return: The string.
  """
  return ("%s,000" % common.delta_str(delta))


def color_message(text, color):
  """Wraps a string with an html/srt FONT tag of the given color.

  :param text: A snark message.
  :param color: An RGB float tuple (value range: 0.0-1.0).
  :return: The wrapped string.
  """
  text = "<font color=\"#%s\">%s</font>" % (common.rgb_to_hex(color), text)
  return text
