import copy
from datetime import datetime, timedelta

from lib import arginfo
from lib import snarkutils


class Config(object):
  def __init__(self, src_config=None):
    object.__init__(self)

    attrib_list = ["parser_name","exporter_name","src_path","dest_path",
                   "first_msg","fudge_time","fudge_users","ignore_users",
                   "end_time","color_enabled","show_time","parser_options",
                   "exporter_options"]

    if (src_config is not None):
      for a in attrib_list:
        setattr(self, a, copy.deepcopy(getattr(src_config, a, None)))
    else:
      for a in attrib_list:
        setattr(self, a, None)

  def get_description(self):
    return "Scroll down to apply changes."

  def get_arginfo(self):
    args = []
    args.append(arginfo.Arg(name="parser_name", type=arginfo.STRING,
                required=True, default=None, choices=snarkutils.list_parsers(), multiple=False,
                description="Parser module name."))
    args.append(arginfo.Arg(name="exporter_name", type=arginfo.STRING,
                required=True, default=None, choices=snarkutils.list_exporters(), multiple=False,
                description="Exporter module name."))
    args.append(arginfo.Arg(name="src_path", type=arginfo.FILE_OR_URL,
                required=False, default=None, choices=None, multiple=False,
                description="Source url/file to parse."))
    args.append(arginfo.Arg(name="dest_path", type=arginfo.FILE,
                required=False, default=None, choices=None, multiple=False,
                description="Destination file to write."))
    args.append(arginfo.Arg(name="first_msg", type=arginfo.STRING,
                required=False, default=None, choices=None, multiple=False,
                description="Optional substring for parsers to expect of the first comment.\nUse this to skip early comments."))
    args.append(arginfo.Arg(name="fudge_time", type=arginfo.TIMEDELTA,
                required=True, default=timedelta(minutes=0, seconds=0), choices=None, multiple=False,
                description="Delay all comments (+/-)."))
    args.append(arginfo.Arg(name="ignore_users", type=arginfo.STRING,
                required=False, default=None, choices=None, multiple=True,
                description="Users to ignore (Example: @steve)."))
    args.append(arginfo.Arg(name="end_time", type=arginfo.TIMEDELTA,
                required=False, default=None, choices=None, multiple=False,
                description="Optional in-movie time to truncate comments (after fudging).\nUse this to skip late comments."))
    args.append(arginfo.Arg(name="color_enabled", type=arginfo.STRING,
                required=True, default="random", choices=["no","random","default"], multiple=False,
                description="Colored subtitles\n  no: there will be no color info.\n  random: assign colors to users randomly.\n  default: let the parser decide.\nAt low resolutions, colored text can be ugly in VLC."))
    args.append(arginfo.Arg(name="show_time", type=arginfo.TIMEDELTA,
                required=True, default=timedelta(minutes=0, seconds=6), choices=None, multiple=False,
                description="Duration each comment appears on-screen."))
    return args

  def apply_current_values_to_args(self, args, parser_namespace=None, exporter_namespace=None):
    """Sets current_value on a given list of arginfo.Args.
    By default, it expects general args from a Config object.
    If one of the namespaces is defined, args will be treated
    as parser/exporter options instead.

    This modifies the args list in-place.
    """
    if (parser_namespace is not None):
      for arg in args:
        if ((parser_namespace + arg.name) in self.parser_options):
          arg.current_value = self.parser_options.get(parser_namespace + arg.name)
    elif (exporter_namespace is not None):
      for arg in args:
        if ((exporter_namespace + arg.name) in self.exporter_options):
          arg.current_value = self.exporter_options.get(exporter_namespace + arg.name)
    else:
      for arg in args:
        if (hasattr(self, arg.name) is True):
          arg.current_value = getattr(self, arg.name)
