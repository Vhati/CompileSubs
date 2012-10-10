import copy
from datetime import datetime, timedelta
import getpass
import htmlentitydefs
import logging
import re
import sys
import weakref
import webbrowser


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


def delta_from_str(s):
  """Constructs a timedelta from a string.

  :param s: A string, as from delta_str().
  :return: The timedelta, or None if invalid.
  """
  result = None
  m = re.match("^(-?)([0-9]+):([0-9]+):([0-9]+)$", s)
  if (m is not None):
    sign_multiplier = (-1 if (m.groups()[0] == "-") else 1)
    hours, minutes, seconds = [(int(s)*sign_multiplier) for s in m.groups()[1:]]
    result = timedelta(hours=hours, minutes=minutes, seconds=seconds)
  else:
    raise ValueError("Invalid timedelta string: \"%s\" should be \"(-?)00:00:00\"." % s)
  return result

def delta_str(delta):
  """Formats a timedelta as a string.
  A timedelta doesn't have a built-in formatter, so this
  computes hh:mm:ss (days are ignored), padded to
  double-digits each. If the time is negative,
  a minus sign is prepended to the string.

  :param delta: A timedelta.
  :return: The string.
  """
  total_seconds = delta_seconds(delta)
  sign = ("" if (total_seconds >= 0) else "-")
  hours, remainder = divmod(abs(total_seconds), 3600)
  minutes, seconds = divmod(remainder, 60)
  result = "%s%02d:%02d:%02d" % (sign, hours, minutes, seconds)

  return result


def delta_seconds(delta):
  """Returns the total seconds in a timedelta.
  Timedeltas lacked a method for this until Python 2.7.

  Negative seconds will really be negative (no more
  normalization).

  :param delta: A timedelta.
  :return: A number.
  """
  return (delta.days*24*3600 + delta.seconds)


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


class SnarksEvent(object):
  """Event to notify listeners of changes to configs and snarks lists.
  An *_ALL flag in the constructor will cause every section flag to be
  included.
  An *_ANY flag will be included when a section flag is present.
  """
  FLAG_SNARKS = "FLAG_SNARKS"
  FLAG_CONFIG_ANY = "FLAG_CONFIG_ANY"
  FLAG_CONFIG_ALL = "FLAG_CONFIG_ALL"
  FLAG_CONFIG_FUDGES = "FLAG_CONFIG_FUDGES"
  FLAG_CONFIG_SHOW_TIME = "FLAG_CONFIG_SHOW_TIME"
  FLAG_CONFIG_PARSERS = "FLAG_CONFIG_PARSERS"
  FLAG_CONFIG_EXPORTERS = "FLAG_CONFIG_EXPORTERS"

  RANGE_APPEND = "RANGE_APPEND"  # Not used.
  RANGE_DELETE = "RANGE_DELETE"  # Not used.
  RANGE_INSERT = "RANGE_INSERT"  # Not used.

  _SECTION_FLAGS = [[FLAG_CONFIG_ALL, FLAG_CONFIG_ANY,
                      [FLAG_CONFIG_FUDGES, FLAG_CONFIG_SHOW_TIME,
                       FLAG_CONFIG_PARSERS, FLAG_CONFIG_EXPORTERS]]]

  def __init__(self, flags):
    object.__init__(self)
    self._source = None
    self._flags = flags
    if (self._flags is None):
      self._flags = []
    elif (self._flags):
      # Expand *_ALL flags.
      for section_list in SnarksEvent._SECTION_FLAGS:
        if (section_list[0] in self._flags):
          for f in section_list[2]:
            if (f not in self._flags):
              self._flags.append(f)  # Add section flag.
      # Add *_ANY flags.
      for section_list in SnarksEvent._SECTION_FLAGS:
        for f in section_list[2]:
          if (f in self._flags):
            if (section_list[1] not in self._flags):
              self._flags.append(section_list[1])  # Add *_ANY.
              break

  def get_source(self):
    return self._source

  def set_source(self, o):
    self._source = o

  def get_flags(self):
    return self._flags

  def clone(self):
    """Returns a shallow copy of this event."""
    e = SnarksEvent(self._flags[:])
    e._source = self._source
    return e

class SnarksWrapper(object):
  """Wraps a snarks list to provide change notifications.
  Listeners are only weakly referenced.
  """
  def __init__(self, config, snarks):
    object.__init__(self)
    self._config_stable = config
    self._config_unstable = None
    self._snarks_stable = snarks
    self._snarks_unstable = None
    self._owner = None
    self._listeners = []

  def checkout(self, owner):
    """Claims temporary ownership to modify wrapped objects.

    :param owner: A str()-friendly object describing the new owner.
    :raises: Exception, if checkout() was already called without a commit().
    """
    assert (owner is not None)
    if (self._owner is not None):
      raise Exception("%s was checked out again before %s has committed." % (self.__class__.__name__, str(self._owner)))

    self._owner = owner

  def commit(self):
    """Allows wrapped objects to be checked out again.
    Unstable modified versions of the objects will be
    set as the new cloneable stable versions.

    :raises: Exception, if checkout() was not called first.
    """
    if (self._owner is None):
      raise Exception("%s was committed while not checked out." % (self.__class__.__name__))

    if (self._config_unstable is not None):
      self._config_stable = self._config_unstable
      self._config_unstable = None
    if (self._snarks_unstable is not None):
      self._snarks_stable = self._snarks_unstable
      self._snarks_unstable = None
    self._owner = None

  def get_config(self):
    """Returns an unstable config that is safe to modify.

    The first call after a checkout(), this will
    be a copy of the last committed object. From
    then on, that same copy will be returned
    until the next commit().

    :raises: Exception, if checkout() was not called first.
    """
    if (self._owner is None):
      raise Exception("%s.get_config() was called while not checked out." % (self.__class__.__name__))

    if (self._config_unstable is None):
      self._config_unstable = copy.deepcopy(self._config_stable)
    return self._config_unstable

  def set_config(self, config):
    """Replaces the unstable config.

    :raises: Exception, if checkout() was not called first.
    """
    if (self._owner is None):
      raise Exception("%s.set_config() was called while not checked out." % (self.__class__.__name__))
    self._config_unstable = config

  def clone_config(self):
    """Returns a deep copy of the last stable version of the config.
    Listeners should get new copies when notified of changes.
    """
    return copy.deepcopy(self._config_stable)

  def get_snarks(self):
    """Returns an unsable snarks list that is safe to modify.

    The first call after a checkout(), this will
    be a copy of the last committed object. From
    then on, that same copy will be returned
    until the next commit().

    :raises: Exception, if checkout() was not called first.
    """
    if (self._owner is None):
      raise Exception("%s.get_snarks() was called while not checked out." % (self.__class__.__name__))

    if (self._snarks_unstable is None):
      self._snarks_unstable = copy.deepcopy(self._snarks_stable)
    return self._snarks_unstable

  def set_snarks(self, snarks):
    """Replaces the unstable snarks list.

    :raises: Exception, if checkout() was not called first.
    """
    if (self._owner is None):
      raise Exception("%s.set_snarks() was called while not checked out." % (self.__class__.__name__))
    self._snarks_unstable = snarks

  def clone_snarks(self):
    """Returns a deep copy of the last stable version of the snarks list.
    Listeners should get new copies when notified of changes.
    """
    return copy.deepcopy(self._snarks_stable)

  def fire_snarks_event(self, e):
    """Notifies all listeners that the snarks list has changed."""
    e = e.clone()
    e.set_source(self)

    for ref in self._listeners:
      l = ref()
      if (l):  # Skip if None or resolving to False.
        l.on_snarks_changed(e.clone())
      else:
        self._listeners.remove(ref)

  def add_snarks_listener(self, listener):
    """Adds a snarks listener.

    :param listener: An object with an on_snarks_changed(snarks_wrapper) method.
    """
    found = False
    for ref in self._listeners:
      l = ref()
      if (l is listener):
        found = True
        break

    if (found is False):
      self._listeners.append(weakref.ref(listener))

  def remove_snarks_listener(self, listener):
    """Removes a snarks listener."""
    for ref in self._listeners:
      l = ref()
      if (l is listener):
        self._listeners.remove(ref)
        break


class Bunch(object):
  """A minimal object that can have attributes."""
  def __init__(self, **kwds):
    self.__dict__.update(kwds)

class Changeling(Bunch):
  """This assigns itself deep copies of all public
  instance attributes from any other object.

  A function attribute will only be shallow copied.
  Class-level variables and functions will not be
  copied.
  """
  def __init__(self, src_obj):
    attribs = [(k,v) for (k,v) in src_obj.__dict__.items() if (not k.startswith("_"))]
    for (k,v) in attribs:
      setattr(self, k, copy.deepcopy(v))

# Changeling's a way to make backup configs, until I
#   decide to replace the module approach with
#   class instances and/or deserialization.


def prompt_func(msg, hidden=False, notice=None, url=None):
  """A replaceable backend to modally prompt for a string from the user."""
  if (notice): print "\n"+ notice
  if (url):
    print "\n"+ url
    try:
      logging.info("Launching browser: %s" % url)
      webbrowser.open_new_tab(url)
    except (webbrowser.Error) as err:
      logging.error("Failed to launch browser: %s." % str(err))
  print ""
  if (hidden):
    return getpass.getpass(msg)
  else:
    return raw_input(msg)

# Backup the original.
_prompt_func = prompt_func

def prompt(msg, hidden=False, notice=None, url=None):
  """A frontend to modally prompt for a string from the user.

  :param msg: The message to display.
  :param hidden: Don't echo, when requesting a password.
  :param notice: Optional descriptive paragraph.
  :param url: Optional hyperlink.
  :return: A string.
  """
  return prompt_func(msg, hidden=hidden, notice=notice, url=url)
