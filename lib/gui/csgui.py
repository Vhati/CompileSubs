import logging
import Queue
import sys
import threading
import webbrowser
import wx

from lib import arginfo
from lib import csconfig
from lib import common
from lib import global_config
from lib import snarkutils
from lib.gui import config_ui
from lib.gui import vlcplayer
from lib.gui import wxlogging


class GuiApp(wx.App):
  def __init__(self, *args, **kwargs):
    self.ACTIONS = ["ACTION_SHOW_CONFIG", "ACTION_SHOW_PLAYER",
                    "ACTION_WARN", "ACTION_DIE"]
    for x in self.ACTIONS: setattr(self, x, x)

    self.custom_args = {}
    for k in self.custom_args.keys():
      if (k in kwargs):
        self.custom_args[k] = kwargs[k]
        del kwargs[k]

    self.done = False  # Indicates to other threads that MainLoop() ended.

    wx.App.__init__(self, *args, **kwargs)  # OnInit() runs here.

  def OnInit(self):
    self._event_queue = Queue.Queue()
    self.log_frame = None
    self.player_frame = None

    # Events.
    self.EVT_EVENT_ENQUEUED_TYPE = wx.NewEventType()
    self.EVT_EVENT_ENQUEUED = wx.PyEventBinder(self.EVT_EVENT_ENQUEUED_TYPE, 1)

    self.Bind(self.EVT_EVENT_ENQUEUED, self.process_event_queue)

    # Guify prompts.
    def new_prompt_func(msg, hidden=False, notice=None, url=None):
      return call_modal(gui_prompt, msg=msg, hidden=False, notice=notice, url=url)
    common.prompt_func = new_prompt_func

    # Setup the log window.
    wx_handler = wxlogging.wxLogHandler(lambda: wx.GetApp().log_frame)
    wx_formatter = logging.Formatter("%(asctime)s %(levelname)s (%(module)s): %(message)s", "%H:%M:%S")
    wx_handler.setFormatter(wx_formatter)
    wx_handler.setLevel(logging.INFO)
    logging.getLogger().addHandler(wx_handler)

    try:
      # Import the config module as an object that can
      # be passed around, and suppress creation of pyc clutter.
      #
      sys.dont_write_bytecode = True
      config = __import__("config")
      sys.dont_write_bytecode = False
      config = common.Changeling(config)  # A copy w/o module baggage.

      snarks = []
      self._snarks_wrapper = common.SnarksWrapper(config, snarks)

      # Don't let config_saver get garbage collected.
      self._config_saver = common.Bunch()
      def on_snarks_changed(e):
        if (common.SnarksEvent.FLAG_CONFIG_ANY not in e.get_flags()):
          return
        try:
          repr_str = snarkutils.config_repr(e.get_source().clone_config())
          with open("./config_gui_backup.py", "w") as fudge_file:
            fudge_file.write("# These settings were auto-saved when the GUI made changes.\n")
            fudge_file.write("# To reuse them next time, rename this file to config.py.\n")
            fudge_file.write("# Otherwise this file will be overwritten.\n\n")
            fudge_file.write(repr_str)
            fudge_file.write("\n")
        except (Exception) as err:
          logging.exception("Failed to save backup config.")

      self._config_saver.on_snarks_changed = on_snarks_changed
      self._snarks_wrapper.add_snarks_listener(self._config_saver)

    except (Exception) as err:
      logging.exception(err)
      return False


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
      old_config = self._snarks_wrapper.clone_config()

      config = self._snarks_wrapper.get_config()
      snarks = self._snarks_wrapper.get_snarks()
      for (k,v) in values_dict.items():
        setattr(config, k, v)

      # Determine what changed, assuming everything, at first.
      # Each section flag may be removed, but we'll keep ANY to be safe.
      event_flags = []
      for section_list in common.SnarksEvent.SECTION_FLAGS:
        if (section_list[0] == common.SnarksEvent.FLAG_CONFIG_ALL):
          for f in section_list[2]:
            if (f not in event_flags):
              event_flags.append(f)  # Add section flag.
          if (section_list[1] not in event_flags):
            event_flags.append(section_list[1])  # Add *_ANY.
        break

      def toggle_flag(event_flags, flag, expression):
        # Sets a flag if expression is True, unsets otherwise.
        if (expression):
          if (flag not in event_flags): event_flags.append(flag)
        else:
          if (flag in event_flags): event_flags.remove(flag)

      if (config.ignore_users != old_config.ignore_users):
        # Unignore the old list, Ignore the new list.
        for snark in snarks:
          if (snark["user"] in config.ignore_users):
            snark["_ignored"] = True
          elif (snark["user"] in old_config.ignore_users):
            snark["_ignored"] = False
        toggle_flag(event_flags, common.SnarksEvent.FLAG_SNARKS, True)

      if (config.fudge_time != old_config.fudge_time):
        diff = config.fudge_time - old_config.fudge_time
        for user in config.fudge_users:
          fudge_list = config.fudge_users[user]
          fudge_list[:] = [(ft[0]+diff, ft[1]) for ft in fudge_list]
        toggle_flag(event_flags, common.SnarksEvent.FLAG_CONFIG_FUDGES, True)

        # Strip cached globally fudged time.
        for snark in snarks:
          snark.pop("_globally fudged time", None)
        snarkutils.gui_fudge_users(config, snarks)
        toggle_flag(event_flags, common.SnarksEvent.FLAG_SNARKS, True)
      else:
        toggle_flag(event_flags, common.SnarksEvent.FLAG_CONFIG_FUDGES, False)

      toggle_flag(event_flags, common.SnarksEvent.FLAG_CONFIG_SHOW_TIME,
                  (config.show_time != old_config.show_time))

      toggle_flag(event_flags, common.SnarksEvent.FLAG_CONFIG_PARSERS,
                  (config.parser_name != old_config.parser_name))

      toggle_flag(event_flags, common.SnarksEvent.FLAG_CONFIG_EXPORTERS,
                  (config.exporter_name != old_config.exporter_name))

      self._snarks_wrapper.commit()

      event = common.SnarksEvent(event_flags)
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

  def show_log_frame(self, parent):
    """Creates and shows a log frame, if it doesn't already exist.

    If parent resolves to False, parent will be set to the
    player_frame, if available.

    If a log frame exists with the same parent, it will gain focus.
    Otherwise, it will be closed, and its text will be appended to
    a new log frame.
    """
    if (not parent):
      parent = None
      if (self.player_frame):
        parent = self.player_frame

    prev_text = None
    if (self.log_frame):
      if (self.log_frame.GetParent() is parent):
        self.log_frame.SetFocus()
      else:
        prev_text = self.log_frame.text.GetValue()
        prev_frame = self.log_frame
        self.log_frame = None
        prev_frame.Close()

    if (not self.log_frame):
      self.log_frame = wxlogging.LogFrame(parent, wx.ID_ANY, "Log")
      self.log_frame.SetSize((700, 200))
      if (prev_text):
        self.log_frame.text.AppendText(prev_text)
      self.log_frame.Center()
      self.log_frame.Show()

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
    ACTION_SHOW_CONFIG(parent,continue_func,destroyed_func)
    ACTION_SHOW_PLAYER()
    ACTION_WARN(message)
    ACTION_DIE()
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
      if (not self.player_frame):
        self.player_frame = vlcplayer.PlayerFrame(None, wx.ID_ANY, "CompileSubs %s" % global_config.VERSION, self._snarks_wrapper)
        self.player_frame.Center()
        self.player_frame.Show()
        self.player_frame.init_vlc()
        self.player_frame.Bind(wx.EVT_WINDOW_DESTROY, self._on_frame_destroyed)

    elif (func_or_name == self.ACTION_WARN):
      if (check_args(["message"])):
        if (self.player_frame):
          self.player_frame.set_status_text(arg_dict["message"], self.player_frame.STATUS_HELP)

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


class PromptDialog(wx.Dialog):
  def __init__(self, *args, **kwargs):
    self.custom_args = {"msg":None,"hidden":False,"notice":None,"url":None}
    for k in self.custom_args.keys():
      if (k in kwargs):
        self.custom_args[k] = kwargs[k]
        del kwargs[k]
    if (self.custom_args["msg"] is None): self.custom_args["msg"] = ""

    wx.Dialog.__init__(self, *args, **kwargs)

    vbox = wx.BoxSizer(wx.VERTICAL)
    vbox.Add((-1,20))
    if (self.custom_args["notice"]):
      notice_label = wx.StaticText(self, wx.ID_ANY, label=self.custom_args["notice"])
      vbox.Add(notice_label, flag=wx.ALIGN_CENTER)
      vbox.Add((-1,15))
    if (self.custom_args["url"]):
      url_btn = wx.HyperlinkCtrl(self, wx.ID_ANY, label="Browser Link", url=self.custom_args["url"])
      url_btn.Bind(wx.EVT_HYPERLINK, self._on_link)
      vbox.Add(url_btn, flag=wx.ALIGN_CENTER)
      vbox.Add((-1,15))

    field_sizer = wx.BoxSizer(wx.HORIZONTAL)
    if (self.custom_args["msg"]):
      msg_label = wx.StaticText(self, wx.ID_ANY, label=self.custom_args["msg"])
      field_sizer.Add(msg_label, flag=wx.ALIGN_CENTER_VERTICAL)
      field_sizer.Add((4,-1))

      if (self.custom_args["hidden"]):
        self._input_field = wx.TextCtrl(self, wx.ID_ANY, style=wx.TE_PASSWORD, size=(250,-1))
      else:
        self._input_field = wx.TextCtrl(self, wx.ID_ANY, size=(250,-1))
    field_sizer.Add(self._input_field, 1, flag=wx.ALIGN_CENTER_VERTICAL)
    vbox.Add(field_sizer, flag=wx.EXPAND|wx.LEFT|wx.RIGHT, border=10)

    vbox.Add((-1,10))

    button_sizer =  self.CreateButtonSizer(wx.OK)
    self.Bind(wx.EVT_BUTTON, self._on_ok, id=wx.ID_YES)
    vbox.Add(button_sizer, flag=wx.ALIGN_CENTER)
    vbox.Add((-1,10))
    self.SetSizer(vbox)

    self._input_field.SetFocus()
    self.Fit()

  def _on_link(self, event):
    try:
      logging.info("Launching browser: %s" % self.custom_args["url"])
      webbrowser.open_new_tab(self.custom_args["url"])
    except (Exception) as err:
      logging.error("Failed to launch browser: %s." % str(err))

  def _on_ok(self, event):
    self.Close()

  def get_value(self):
    return self._input_field.GetValue()


def gui_prompt(msg, hidden=False, notice=None, url=None):
  """Shows a PromptDialog and returns the user-provided value.
  This must be called from the GUI thread.
  """
  result = None

  parent = None
  if (wx.GetApp().player_frame): parent = wx.GetApp().player_frame

  d = PromptDialog(parent, wx.ID_ANY, "Prompt", msg=msg, hidden=hidden, notice=notice, url=url)
  d.Center()
  if (d.ShowModal() == wx.ID_OK):
    result = d.get_value()
  d.Destroy()

  return result


def call_modal(modal_func, *args, **kwargs):
  """Executes an arbitrary function in the GUI thread modally.
  This is thread-safe. If called from the GUI thread, nothing
  special happens. Otherwise the calling thread will block
  while the function is scheduled in the GUI thread, and will
  resume after it has returned or raised an exception. Then
  this will return that value or re-raise that exception in
  the original thread.

  Any additional args will be passed to the function.

  :param modal_func: A function to call in the GUI thread.
  :returns: Whatever modal_func returns, or None if keep-alive becomes False.
  :raises: Whatever modal_func raises.
  """
  if (wx.Thread_IsMain()):
    return modal_func(*args, **kwargs)
  else:
    # Blocking until the global cleanup_handler kicks in
    # is easier than the extra tracking to send a second
    # GUI signal to close the popup it when a
    # killable thread stops living.
    keep_alive_func = global_config.keeping_alive

    messenger = common.Bunch()
    modal_event = threading.Event()

    def main_code():
      try:
        messenger.result = modal_func(*args, **kwargs)
      except (Exception) as err:
        _, messenger.exception, messenger.traceback = sys.exc_info()
      modal_event.set()

    wx.CallAfter(main_code)
    while (keep_alive_func()):
      modal_event.wait(0.5)
      if (modal_event.is_set()): break

    if (modal_event.is_set()):
      try:
        return messenger.result
      except (AttributeError) as err:
        tb = messenger.traceback
        del messenger.traceback
        raise type(messenger.exception), messenger.exception, tb
    else:
      # Keep-alive returned False and interrupted the wait.
      return None
