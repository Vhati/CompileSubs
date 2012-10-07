import logging
import Queue
import wx

from lib import arginfo
from lib import csconfig
from lib import common
from lib import global_config
from lib import snarkutils
from lib.gui import config_ui
from lib.gui import vlcplayer


class GuiApp(wx.App):
  def __init__(self, *args, **kwargs):
    self.ACTIONS = ["ACTION_SHOW_CONFIG", "ACTION_SHOW_PLAYER",
                    "ACTION_DIE"]
    for x in self.ACTIONS: setattr(self, x, x)

    self.custom_args = {"snarks_wrapper":None}
    for k in self.custom_args.keys():
      if (k in kwargs):
        self.custom_args[k] = kwargs[k]
        del kwargs[k]

    self.done = False  # Indicates to other threads that MainLoop() ended.

    wx.App.__init__(self, *args, **kwargs)  # OnInit() runs here.

  def OnInit(self):
    self._snarks_wrapper = self.custom_args["snarks_wrapper"]
    self._event_queue = Queue.Queue()
    self.player_frame = None

    # Events.
    self.EVT_EVENT_ENQUEUED_TYPE = wx.NewEventType()
    self.EVT_EVENT_ENQUEUED = wx.PyEventBinder(self.EVT_EVENT_ENQUEUED_TYPE, 1)

    self.Bind(self.EVT_EVENT_ENQUEUED, self.process_event_queue)


    def config_continue_callback():
      self.invoke_later(self.ACTION_SHOW_PLAYER, {})
      self.process_event_queue(None)  # Don't let the app expire.

    self.invoke_later(self.ACTION_SHOW_CONFIG, {"parent":None, "continue_func":config_continue_callback, "destroyed_func":None})
    self.process_event_queue(None)  # Don't let the app expire.


    return True

  def _on_frame_destroyed(self, e):
    source = e.GetEventObject()
    if (source is self.player_frame):
      self.player_frame = None
    if (e is not None): e.Skip(True)

  def create_config_sections(self):
    """Returns a list of sections to pass to a config_ui.ConfigFrame.
    Each subsection has an apply callback that will modify the
    SnarksWrapper-enclosed config.
    """
    def config_subsection_callback(values_dict):
      self._snarks_wrapper.checkout(self.__class__.__name__)
      config = self._snarks_wrapper.get_config()
      for (k,v) in values_dict.items():
        setattr(config, k, v)
      self._snarks_wrapper.commit()

      event = common.SnarksEvent([common.SnarksEvent.FLAG_CONFIG_ALL])
      self._snarks_wrapper.fire_snarks_event(event)

    config = csconfig.Config(src_config=self._snarks_wrapper.clone_config())
    config_desc = config.get_description()
    config_args = config.get_arginfo()
    config.apply_current_values_to_args(config_args)

    config_section = config_ui.ConfigSection("General")
    parsers_section = config_ui.ConfigSection("Parsers")
    exporters_section = config_ui.ConfigSection("Exporters")

    config_section.append_subsection(config_ui.ConfigSubSection("General", description=config_desc, args=config_args, apply_func=config_subsection_callback))

    for parser_name in snarkutils.list_parsers():
      parsers_pkg = __import__("lib.parsers", globals(), locals(), [parser_name])
      parser_mod = getattr(parsers_pkg, parser_name)
      parser_desc = parser_mod.get_description()
      parser_args = parser_mod.get_arginfo()
      config.apply_current_values_to_args(parser_args, parser_namespace=parser_mod.ns)

      def subsection_callback(values_dict, ns=parser_mod.ns):
        self._snarks_wrapper.checkout(self.__class__.__name__)
        config = self._snarks_wrapper.get_config()
        for (k,v) in values_dict.items():
          config.parser_options[ns+k] = v
        self._snarks_wrapper.commit()

        event = common.SnarksEvent([common.SnarksEvent.FLAG_CONFIG_PARSERS])
        self._snarks_wrapper.fire_snarks_event(event)
      parsers_section.append_subsection(config_ui.ConfigSubSection(parser_name, description=parser_desc, args=parser_args, apply_func=subsection_callback))

    for exporter_name in snarkutils.list_exporters():
      exporters_pkg = __import__("lib.exporters", globals(), locals(), [exporter_name])
      exporter_mod = getattr(exporters_pkg, exporter_name)
      exporter_desc = exporter_mod.get_description()
      exporter_args = exporter_mod.get_arginfo()
      config.apply_current_values_to_args(exporter_args, exporter_namespace=exporter_mod.ns)

      def subsection_callback(values_dict, ns=exporter_mod.ns):
        self._snarks_wrapper.checkout(self.__class__.__name__)
        config = self._snarks_wrapper.get_config()
        for (k,v) in values_dict.items():
          config.exporter_options[ns+k] = v
        self._snarks_wrapper.commit()

        event = common.SnarksEvent([common.SnarksEvent.FLAG_CONFIG_EXPORTERS])
        self._snarks_wrapper.fire_snarks_event(event)
      exporters_section.append_subsection(config_ui.ConfigSubSection(exporter_name, description=exporter_desc, args=exporter_args, apply_func=subsection_callback))
    sections = [config_section, parsers_section, exporters_section]

    return sections

  def process_event_queue(self, event):
    """Processes every pending event on the queue."""
    func_or_name, arg_dict = None, None
    while (True):
      try:
        func_or_name, arg_dict = self._event_queue.get_nowait()
      except (Queue.Empty) as err:
        break
      else:
        self._process_event(func_or_name, arg_dict)

  def _process_event(self, func_or_name, arg_dict):
    """Processes events queued via invoke_later().
    ACTION_DIE
    """
    def check_args(args):
      for arg in args:
        if (arg not in arg_dict):
          logging.error("Missing %s arg queued to %s %s." % (arg, self.__class__.__name__, func_or_name))
          return False
      return True

    if (hasattr(func_or_name, "__call__")):
      func_or_name(arg_dict)

    elif (func_or_name == self.ACTION_SHOW_CONFIG):
      if (check_args(["parent","continue_func","destroyed_func"])):
        # Check that parent wasn't already destroyed.
        if (arg_dict["parent"] is None or arg_dict["parent"]):
          sections = self.create_config_sections()
          config_frame = config_ui.ConfigFrame(arg_dict["parent"], wx.ID_ANY, "Configuration", sections=sections, continue_func=arg_dict["continue_func"])
          config_frame.Center()
          config_frame.Show()

          if (arg_dict["destroyed_func"] is not None):
            config_frame.Bind(wx.EVT_WINDOW_DESTROY, arg_dict["destroyed_func"])

    elif (func_or_name == self.ACTION_SHOW_PLAYER):
      if (self.player_frame is None):
        self.player_frame = vlcplayer.PlayerFrame(None, wx.ID_ANY, "CompileSubs %s" % global_config.VERSION, self._snarks_wrapper)
        self.player_frame.Center()
        self.player_frame.Show()
        self.player_frame.init_vlc()
        self.player_frame.Bind(wx.EVT_WINDOW_DESTROY, self._on_frame_destroyed)

    elif (func_or_name == self.ACTION_DIE):
      # Close all top windows and let MainLoop expire.
      for w in wx.GetTopLevelWindows(): w.Close()

  def invoke_later(self, func_or_name, arg_dict):
    """Schedules an action to occur in this thread (thread-safe)."""
    self._event_queue.put((func_or_name, arg_dict))

    # PyCommandEvent would propagate.
    event = wx.PyCommandEvent(self.EVT_EVENT_ENQUEUED_TYPE, wx.ID_ANY)
    wx.PostEvent(self, event)
    #wx.CallAfter(self.process_event_queue, None)
