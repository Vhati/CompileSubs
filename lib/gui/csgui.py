import logging
import Queue
import wx

from lib import common
from lib import global_config
from lib.gui import vlcplayer


class GuiApp(wx.App):
  def __init__(self, *args, **kwargs):
    self.ACTIONS = ["ACTION_DIE"]
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

    self.player_frame = vlcplayer.PlayerFrame(None, wx.ID_ANY, "CompileSubs %s" % global_config.VERSION, self._snarks_wrapper)
    self.player_frame.Centre()
    self.player_frame.Show()
    self.player_frame.init_vlc()

    def on_player_frame_destroyed(e):
      self.player_frame = None
      if (e is not None): e.Skip(True)
    self.player_frame.Bind(wx.EVT_WINDOW_DESTROY, on_player_frame_destroyed)

    return True

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

    elif (func_or_name == self.ACTION_DIE):
      # Close all top windows and let MainLoop expire.
      if (self.player_frame is not None):
        self.player_frame._on_close(None)

  def invoke_later(self, func_or_name, arg_dict):
    """Schedules an action to occur in this thread (thread-safe)."""
    self._event_queue.put((func_or_name, arg_dict))

    # PyCommandEvent would propagate.
    event = wx.PyCommandEvent(self.EVT_EVENT_ENQUEUED_TYPE, wx.ID_ANY)
    wx.PostEvent(self, event)
    #wx.CallAfter(self.process_event_queue, None)
