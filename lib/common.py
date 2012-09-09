import getpass
import htmlentitydefs
import logging
import re
import sys


def html_unescape(text):
  """Removes HTML or XML character references and entities
  from a text string.
  http://effbot.org/zone/re-sub.htm#unescape-html

  :param text: The HTML (or XML) source text.
  :return: The plain text, as a Unicode string, if necessary.
  """
  def fixup(m):
    text = m.group(0)
    if text[:2] == "&#":
      # character reference
      try:
        if text[:3] == "&#x":
          return unichr(int(text[3:-1], 16))
        else:
          return unichr(int(text[2:-1]))
      except ValueError:
        pass
    else:
      # named entity
      try:
        text = unichr(htmlentitydefs.name2codepoint[text[1:-1]])
      except KeyError:
        pass
    return text # leave as is
  return re.sub("&#?\w+;", fixup, text)


def asciify(utext):
  """Converts a unicode string to ascii, substituting some chars.

  :param utext: A unicode string to convert (harmless if already ascii).
  :return: An asciified string.
  """
  # To check a char: http://www.eki.ee/letter/chardata.cgi?ucode=2032
  utext = utext.replace(u"\u2013", "-")
  utext = utext.replace(u"\u2014", "-")
  utext = utext.replace(u"\u2018", "'")
  utext = utext.replace(u"\u2019", "'")
  utext = utext.replace(u"\u2032", "'")
  utext = utext.replace(u"\u201c", "\"")
  utext = utext.replace(u"\u201d", "\"")
  utext = utext.replace(u"\u2026", "...")
  # Replace every other non-ascii char with "?".
  text = utext.encode("ASCII", "replace")
  return text


def delta_str(delta):
  """Formats a timedelta as a string.
  A timedelta doesn't have a built-in formatter, so this
  computes hh:mm:ss (days are ignored), padded to
  double-digits each. Negative times, which shouldn't
  happen, are given a minus sign.

  :return: The string.
  """
  sign = ("" if (abs(delta) == delta) else "-")  # Shouldn't be minuses!
  hours, remainder = divmod(abs(delta).seconds, 3600)
  minutes, seconds = divmod(remainder, 60)
  result = "%s%02d:%02d:%02d" % (sign, hours, minutes, seconds)

  return result


def hex_to_rgb(hex_color):
  """Converts a hex color string into an RGB float tuple.

  :param hex_color: A  six-character hex color string (00-FF/00-ff).
  :return: An RGB float tuple (0.0-1.0).
  """
  return tuple([int(cc,16)/float(255) for cc in [hex_color[0:2], hex_color[2:4], hex_color[4:6]]])


def rgb_to_hex(rgb_color):
  """Converts an RGB float tuple into a hex string.

  :param rgb_color: An RGB float tuple (0.0-1.0).
  :return: A six-character hex string (00-ff).
  """
  return "".join([("%02x" % (n*255)) for n in rgb_color])


class CompileSubsException(Exception):
  pass
class ParserError(CompileSubsException):
  pass
class ExporterError(CompileSubsException):
  pass


class Bunch:
  """A minimal object that can have attributes."""
  def __init__(self, **kwds):
    self.__dict__.update(kwds)

class Changeling(Bunch):
  """This assigns itself deep copies of all public
  instance attributes from any other object.

  A function attribute will only be shallow copied.
  This does not copy class variables or class functions.
  """
  def __init__(self, src_obj):
    import copy

    attribs = [(k,v) for (k,v) in src_obj.__dict__.items() if (not k.startswith("_"))]
    for (k,v) in attribs:
      setattr(self, k, copy.deepcopy(v))

# Changeling's a way to make backup configs, until I
#   decide to replace the module approach with
#   class instances and/or deserialization.


# Replaceable backend to prompt for a string.
prompt_func = lambda msg: raw_input(msg)

# Replaceable backend to prompt for a password.
hidden_prompt_func = lambda msg: getpass.getpass(msg)

def prompt(msg, hidden=False):
  """A frontend to prompt for a string from the user.

  :param msg: The message to display.
  :param hidden: Don't echo, when requesting a password.
  :return: A string.
  """
  if (hidden):
    return hidden_prompt_func(msg)
  else:
    return prompt_func(msg)
