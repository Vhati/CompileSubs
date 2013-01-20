import contextlib
from datetime import datetime, timedelta
import pkgutil
import random
import shutil
import string
import StringIO

from lib import common
from lib import global_config


random.seed()


def config_remove_user_fudge(config, user, bookmark_delta):
  """Removes per-user fudges at a specific time from a config object.

  :param config: A config to modify.
  :param user: The user to fudge.
  :param bookmark_delta: The first timedelta of the pair in config.py.
  """
  fudge_list = config.fudge_users[user]
  fudge_list[:] = [x for x in fudge_list if x[0] != bookmark_delta]

def config_add_user_fudge(config, user, fudge_tuple):
  """Adds a per-user fudge to a config object.
  Any existing fudge at that time will be removed.
  Streaks of identical fudge amounts will be
  consolidated.

  :param config: A config to modify.
  :param user: The user to fudge.
  :param fudge_tuple: (bookmark, amount) timedeltas as in config.py.
  """
  fudge_list = None
  if (user not in config.fudge_users):
    config.fudge_users[user] = []
  fudge_list = config.fudge_users[user]

  # Remove any existing fudge at that time.
  fudge_list[:] = [x for x in fudge_list if x[0] != fudge_tuple[0]]
  fudge_list.append(fudge_tuple)
  fudge_list[:] = sorted(fudge_list, key=lambda k: k[0])

  # Consolidate streaks of identical fudge amounts.
  for i in range(len(fudge_list)-1, 0, -1):
    if (fudge_list[i][1] == fudge_list[i-1][1]):
      del fudge_list[i]


def config_repr(config):
  """Returns a pretty repr string of a config."""
  config_template = None
  config_strings = {}

  with open("./share/config_template.txt", "r") as f:
    config_template = f.read()

  # Strings. (repr() is safe for int, boolean and None)
  for x in ["parser_name", "exporter_name", "src_path", "dest_path", "first_msg", "color_enabled"]:
    config_strings[x] = repr(getattr(config, x))

  # String lists.
  for x in ["ignore_users"]:
    config_strings[x] = repr(getattr(config, x))

  # Timedeltas.
  for x in ["fudge_time", "end_time", "show_time"]:
    config_strings[x] = delta_repr(getattr(config, x))

  results = ["fudge_users = {}"]
  for user in config.fudge_users:
    fudge_strs = []
    for fudge_tuple in config.fudge_users[user]:
      fudge_strs.append("(%s)" % ", ".join(delta_repr(x) for x in fudge_tuple))
    if (len(fudge_strs) == 0): continue
    results.append("fudge_users[\"%s\"] = [%s]" % (user, (",\n" + (" "*(19+len(user)))).join(fudge_strs)))
  config_strings["fudge_users_block"] = "\n".join(results)

  results = ["parser_options = {}"]
  for k in sorted(config.parser_options.keys()):
    option_value = config.parser_options[k]
    if (isinstance(option_value, timedelta)):
      results.append("parser_options[%s] = %s" % (repr(k), delta_repr(option_value)))
    elif (isinstance(option_value, datetime)):
      results.append("parser_options[%s] = %s" % (repr(k), datetime_repr(option_value)))
    else:
      results.append("parser_options[%s] = %s" % (repr(k), repr(option_value)))
  config_strings["parser_options_block"] = "\n".join(results)

  results = ["exporter_options = {}"]
  for k in sorted(config.exporter_options.keys()):
    option_value = config.exporter_options[k]
    if (isinstance(option_value, timedelta)):
      results.append("exporter_options[%s] = %s" % (repr(k), delta_repr(option_value)))
    elif (isinstance(option_value, datetime)):
      results.append("exporter_options[%s] = %s" % (repr(k), datetime_repr(option_value)))
    else:
      results.append("exporter_options[%s] = %s" % (repr(k), repr(option_value)))
  config_strings["exporter_options_block"] = "\n".join(results)

  return string.Template(config_template).substitute(config_strings)

def delta_repr(delta):
  """Returns a pretty repr string of a timedelta.
  If delta is None, repr(None) will be returned.
  """
  if (delta is None): return repr(None)

  minutes, seconds = divmod(common.delta_seconds(delta), 60)

  return "timedelta(minutes=%d, seconds=%d)" % (minutes, seconds)

def datetime_repr(dt):
  """Returns a pretty repr string of a datetime."""
  return "datetime(%d, %d, %d, %d, %d)" % (dt.year, dt.month, dt.day, dt.hour, dt.minute)


def get_parser(parser_name):
  """Returns a parser by name."""
  parsers_pkg = __import__("lib.parsers", globals(), locals(), [parser_name])
  parser_mod = getattr(parsers_pkg, parser_name)
  return parser_mod

def get_exporter(exporter_name):
  """Returns an exporter by name."""
  exporters_pkg = __import__("lib.exporters", globals(), locals(), [exporter_name])
  exporter_mod = getattr(exporters_pkg, exporter_name)
  return exporter_mod

def get_subsystem(subsystem_name):
  """Returns a subsystem by name."""
  subsystems_pkg = __import__("lib.subsystems", globals(), locals(), [subsystem_name])
  subsystem_mod = getattr(subsystems_pkg, subsystem_name)
  return subsystem_mod

def init_subsystems(subsystem_names, keep_alive_func=None, sleep_func=None):
  """Calls init() on each in a list of subsystems.

  :param keep_alive_func: Optional replacement to get an abort boolean.
  :param sleep_func: Optional replacement to sleep N seconds.
  :raises: CompileSubsException, afterward, if any failed.
  """
  if (keep_alive_func is None): keep_alive_func = global_config.keeping_alive
  if (sleep_func is None): sleep_func = global_config.nap

  failures = []
  for s in subsystem_names:
    if (keep_alive_func() is False): break
    ready = False
    try:
      ready = get_subsystem(s).init(keep_alive_func=keep_alive_func, sleep_func=sleep_func)
    except (Exception) as err:
      logging.exception("Subsystem import or init failed.")
    if (ready is False):
      failures.append(s)

  if (len(failures) > 0):
    raise common.CompileSubsException("Failed to initialize required subsystems: %s." % (", ".join(failures)))


def parse_snarks(config, keep_alive_func=None, sleep_func=None):
  """Returns a list of snark dicts{user,msg,date} from a parser.
  More keys might be present, depending on the parser.
  These snarks do NOT have a "time" key.

  If the parser requires any subsystems, they will be init'd.

  :param keep_alive_func: Optional replacement to get an abort boolean.
  :param sleep_func: Optional replacement to sleep N seconds.
  :raises: ParserError, CompileSubsException
  """
  if (keep_alive_func is None): keep_alive_func = global_config.keeping_alive
  if (sleep_func is None): sleep_func = global_config.nap

  parser_mod = get_parser(config.parser_name)
  init_subsystems(parser_mod.required_subsystems, keep_alive_func=keep_alive_func, sleep_func=sleep_func)

  if (keep_alive_func() is False):
    raise common.ParserError("Parsing was interrupted.")

  snarks = parser_mod.fetch_snarks(config.src_path, config.first_msg, config.parser_options, keep_alive_func=keep_alive_func, sleep_func=sleep_func)

  return snarks


def gui_preprocess_snarks(config, snarks):
  """Performs initial processing of recently parsed snarks.

  No early/late pruning takes place. The result will be
  suitable for gui_fudge_users().

  A "_globally fudged time" key will be added, representing
  an in-movie offset from the first snark's "date", plus
  any global fudging, but NOT user fudging. A "time" key
  is also added with a similar value, but that may be
  subject to user fudging later.

  A boolean "_ignored" key will be added: True for any
  snark that's from an ignored user, False otherwise.

  No "color" is added.

  This will modify the snarks list in-place.
  """
  # Sort the msgs by their real-world date.
  snarks[:] = sorted(snarks, key=lambda k: k["date"])

  # Add in-movie time info to them.
  for snark in snarks:
    snark["_globally fudged time"] = snark["date"] - snarks[0]["date"] + config.fudge_time
    snark["time"] = snark["date"] - snarks[0]["date"] + config.fudge_time

  # Sort the msgs by their in-movie time.
  snarks[:] = sorted(snarks, key=lambda k: k["time"])

  # Ignore users.
  for snark in snarks:
    if (snark["user"] in config.ignore_users):
      snark["_ignored"] = True
    else:
      snark["_ignored"] = False


def gui_fudge_users(config, snarks):
  """Sets snarks' "time", including global and user fudging.

  If the "_globally fudged time" key is present,
  some math will be bypassed. Otherwise, it will
  be created using the offset since the first
  snark's "date" and the config's global fudge.

  That value will then be added to the config's
  per-user fudges to set "time".

  This will modify the snarks list in-place.
  """
  # Sort the msgs by their real-world date (to obtain the first snark).
  snarks[:] = sorted(snarks, key=lambda k: k["date"])

  for snark in snarks:
    # Revert each snark's time to its globally fudged time.
    if ("_globally fudged time" not in snark):
      snark["_globally fudged time"] = snark["date"] - snarks[0]["date"] + config.fudge_time
    snark["time"] = snark["_globally fudged time"]

    # Search backward through a user's delays for one in the recent past.
    if (snark["user"] in config.fudge_users):
      for (bookmark, fudge_value) in reversed(config.fudge_users[snark["user"]]):
        if (snark["time"] >= bookmark):
          snark["time"] += fudge_value
          break

  # Sort the msgs by their in-movie time.
  snarks[:] = sorted(snarks, key=lambda k: k["time"])


def gui_postprocess_snarks(config, snarks):
  """Performs remaining processing of snarks.
  Any snark that's early or late will be removed.
  Any snark with an "_ignored" key that's True
  will be removed.

  The result will be suitable for export_snarks().

  If enabled in config, a "color" key is added,
  an RGB float tuple (0.0-1.0), assigned randomly.

  This will modify the snarks list in-place.
  """
  # Omit ignored snarks.
  snarks[:] = [s for s in snarks if (not ("_ignored" in s and s["_ignored"]))]

  # Omit snarks that got shifted into negative times.
  snarks[:] = [x for x in snarks if (abs(x["time"]) == x["time"])]

  # Omit snarks beyond the end time, if set.
  if (config.end_time is not None):
    snarks[:] = [x for x in snarks if (x["time"] <= config.end_time)]

  # Sort the msgs by their in-movie time.
  snarks[:] = sorted(snarks, key=lambda k: k["time"])

  # Assign unique colors, and paint each snark.
  if (config.color_enabled == "random"):
    unique_users = set(x["user"] for x in snarks)
    unique_colors = get_random_colors(len(unique_users))
    #write_palette_preview("./preview.html", unique_colors)

    color_users = dict(zip(unique_users, unique_colors))
    for snark in snarks:
      snark["color"] = color_users[snark["user"]]
  elif (config.color_enabled == "no"):
    for snark in snarks:
      if ("color" in snark): del snark["color"]


def process_snarks(config, snarks):
  """Adds info to, and fudges, a list of recently parsed snarks.
  Any snark that's early, late, or from an ignored user will be
  removed. The result will be suitable for export_snarks().

  A "time" key will be added, representing an in-movie offset
  from the first snark's "date", plus any global fudging,
  plus any user fudging.

  If enabled in config, "color" is added, an RGB float tuple
  (0.0-1.0), assigned randomly.

  This will modify the snarks list in-place.
  """
  # Sort the msgs by their real-world date.
  snarks[:] = sorted(snarks, key=lambda k: k["date"])

  # Add in-movie time info to them.
  for snark in snarks:
    snark["time"] = snark["date"] - snarks[0]["date"] + config.fudge_time

    # Search backward through a user's delays for one in the recent past.
    if (snark["user"] in config.fudge_users):
      for (bookmark, fudge_value) in reversed(config.fudge_users[snark["user"]]):
        if (snark["time"] >= bookmark):
          snark["time"] += fudge_value
          break

  # Omit snarks from ignored users.
  snarks[:] = [s for s in snarks if (s["user"] not in config.ignore_users)]

  # Omit snarks that got shifted into negative times.
  snarks[:] = [x for x in snarks if (abs(x["time"]) == x["time"])]

  # Omit snarks beyond the end time, if set.
  if (config.end_time is not None):
    snarks[:] = [x for x in snarks if (x["time"] <= config.end_time)]

  # Sort the msgs by their in-movie time.
  snarks[:] = sorted(snarks, key=lambda k: k["time"])

  # Assign unique colors, and paint each snark.
  if (config.color_enabled == "random"):
    unique_users = set(x["user"] for x in snarks)
    unique_colors = get_random_colors(len(unique_users))
    #write_palette_preview("./preview.html", unique_colors)

    color_users = dict(zip(unique_users, unique_colors))
    for snark in snarks:
      snark["color"] = color_users[snark["user"]]
  elif (config.color_enabled == "no"):
    for snark in snarks:
      if ("color" in snark): del snark["color"]


def export_snarks(config, snarks, keep_alive_func=None, sleep_func=None):
  """Sends a list of processed snark dicts to an exporter.
  The snarks must, at minimum, contain {user,msg,time}.

  Whatever the exporter writes to its dest_file arg will
  be buffered. Afterward, if the exporter's uses_dest_file
  attribute is True, that buffer will be written to
  an actual file.

  If the exporter requires any subsystems, they will be init'd.

  :raises: ExporterError, CompileSubsException
  """
  if (keep_alive_func is None): keep_alive_func = global_config.keeping_alive
  if (sleep_func is None): sleep_func = global_config.nap

  exporter_mod = get_exporter(config.exporter_name)
  init_subsystems(exporter_mod.required_subsystems, keep_alive_func=keep_alive_func, sleep_func=sleep_func)

  if (keep_alive_func() is False):
    raise common.ExporterError("Exporting was interrupted.")

  with contextlib.closing(StringIO.StringIO()) as buf:
    exporter_mod.write_snarks(buf, snarks, config.show_time, config.exporter_options, keep_alive_func=keep_alive_func, sleep_func=sleep_func)
    buf.seek(0)

    if (keep_alive_func() is False):
      raise common.ExporterError("Exporting was interrupted.")

    if (config.dest_path and exporter_mod.uses_dest_file):
      with open(config.dest_path, "wb") as dest_file:
        shutil.copyfileobj(buf, dest_file)


def list_parsers():
  """Returns a list of parser module names."""
  import lib.parsers
  result = [name for (module_loader, name, ispkg)
            in pkgutil.iter_modules(path=lib.parsers.__path__)
            if (not ispkg and name != "example_stub")]
  return result

def list_exporters():
  """Returns a list of exporter module names."""
  import lib.exporters
  result = [name for (module_loader, name, ispkg)
            in pkgutil.iter_modules(path=lib.exporters.__path__)
            if (not ispkg and name != "example_stub")]
  return result


def get_random_colors(count):
  """Gets a list of arbitrary colors.
   I had a fancy HSV randomizer with the colorsys module,
   but it was hit and miss. So now there's a prefab list.
     http://jsfiddle.net/k8NC2/1/
     http://stackoverflow.com/questions/470690/how-to-automatically-generate-n-distinct-colors

  :param count: The number of colors needed (too many, and you'll get white).
  :return: A list of RGB float tuples (0.0-1.0).
  """
  color_library = [("white", "FFFFFF"),
                   ("kelly-vivid-yellow", "FFB300"),
                   ("kelly-strong-purple", "803E75"),
                   #("kelly-vivid-orange", "FF6800"),
                   ("kelly-very-light-blue", "A6BDD7"),
                   ##("kelly-vivid-red", "C10020"),
                   ("kelly-grayish-yellow", "CEA262"),
                   #("kelly-medium-gray", "817066"),
                   ("kelly-vivid-green", "007D34"),
                   #("kelly-strong-purplish-pink", "F6768E"),
                   ("kelly-strong-blue", "00538A"),
                   #("kelly-strong-yellowish-pink", "FF7A5C"),
                   ##("kelly-strong-violet", "53377A"),
                   #("kelly-vivid-orange-yellow", "FF8E00"),
                   #("kelly-strong-purplish-red", "B32851"),
                   #("kelly-vivid-greenish-yellow", "F4C800"),
                   ##("kelly-strong-reddish-brown", "7F180D"),
                   #("kelly-vivid-yellowish-green", "93AA00"),
                   ##("kelly-deep-yellowish-brown", "593315"),
                   #("kelly-reddish-orange", "F13A13"),
                   ##("kelly-dark-olive-green", "232C16"),
                   #("boynton-blue", "0000FF"),
                   #("boynton-red", "FF0000"),
                   ##("boynton-green", "00FF00"),
                   ##("boynton-yellow", "FFFF00"),
                   ##("boynton-magenta", "FF00FF"),
                   ##("boynton-pink", "FF8080"),
                   ("boynton-gray", "808080"),
                   #("boynton-brown", "800000"),
                   ##("boynton-orange", "FF8000"),
                   ("softened-pink", "CC8080"),
                   ("softened-yellow", "FECC5A"),
                   ##("softened-red", "C71E1E"),
                   ("softened-magenta", "CC00CC"),
                   ("softened-orange", "CC8000"),
                   ("softened-green", "00CC00"),
                   ("lighter-yellowish-brown", "795335"),
                   ("lighter-strong-violet", "73579A"),
                   ("kelly-pale-green", "409565"),
                   ("lighterer-yellowish-brown", "997355"),
                   ("lighterer-strong-violet", "9579BC"),
                   ("lighter-goldenrod", "DEBC4A")
                   ]
  random.shuffle(color_library)
  color_library *= (count // len(color_library)) + 1

  result = [common.hex_to_rgb(y) for (x,y) in color_library[:count]]

  return result


def write_palette_preview(path, unique_colors):
  """Dumps colors to a sanity-preserving html file for eyeballing.
  A relic from debugging random palettes.

  :param path: A file path to write to.
  :param unique_colors: A list of RGB float tuples.
  """
  out_file = open(path, 'w')
  out_file.write("<html><body>\n");
  for color in unique_colors:
    out_file.write("<font color=\"#%s\"><b>#########</b></font><br />\n" % (common.rgb_to_hex(color)));
  out_file.write("</body></html>");
  out_file.close()
