import logging
import re
import wx
import wx.lib.dialogs
import wx.lib.newevent


LogMsgEvent, EVT_LOG_MSG = wx.lib.newevent.NewEvent()


class wxLogHandler(logging.Handler):
  """A logging handler that finds and notifies a wx object."""

  def __init__(self, get_log_dest_func):
    """Constructor.
    Passing a lambda wrapping wx.GetApp().etc is recommended.

    :param get_log_dest_func: A function that returns an EvtHandler (e.g., window).
    """
    logging.Handler.__init__(self)
    self._get_log_dest_func = get_log_dest_func
    self.level = logging.DEBUG

  def flush(self):
    pass

  def emit(self, record):
    try:
      msg = self.format(record)
      event = LogMsgEvent(message=msg,levelname=record.levelname)

      def after_func(get_log_dest_func=self._get_log_dest_func, event=event):
        log_dest = get_log_dest_func()
        if (log_dest):
          wx.PostEvent(log_dest, event)
      wx.CallAfter(after_func)

    except (Exception) as err:
      sys.stderr.write("Error: %s failed while emitting a log record (%s): %s." % (self.__class__.__name__, repr(record), err.reason))


class LogFrame(wx.Frame):
  """A scrollable log window.
  If the caret is at the end, the log will autoscroll.
  """
  def __init__(self, *args, **kwargs):
    wx.Frame.__init__(self, *args, **kwargs)

    self._pane = wx.Panel(self)
    pane_sizer = wx.BoxSizer(wx.VERTICAL)
    self._pane.SetSizer(pane_sizer)

    log_font = wx.Font(9, wx.FONTFAMILY_MODERN, wx.NORMAL, wx.FONTWEIGHT_NORMAL)

    self.text = wx.TextCtrl(self._pane, wx.ID_ANY, style=wx.TE_MULTILINE|wx.TE_READONLY)
    self.text.SetFont(log_font)
    pane_sizer.Add(self.text, 1, flag=wx.EXPAND)

    sizer = wx.BoxSizer(wx.VERTICAL)
    sizer.Add(self._pane, 1, flag=wx.EXPAND)
    self.SetSizer(sizer)

    self.Bind(EVT_LOG_MSG, self.on_log_msg)

  def on_log_msg(self, e):
    try:
      msg = re.sub("\r\n?", "\n", e.message)

      current_pos = self.text.GetInsertionPoint()
      end_pos = self.text.GetLastPosition()
      autoscroll = (current_pos == end_pos)

      # Some bug workarounds to scroll to the end.
      # http://sourceforge.net/p/wxwindows/bugs/708/
      # http://stackoverflow.com/questions/153989/how-do-i-get-the-scroll-position-range-from-a-wx-textctrl-control-in-wxpython/155781#155781
      # http://wxpython-users.1045709.n5.nabble.com/Scrolling-a-wxTextCtrl-as-text-is-added-with-AppendText-td2294276.html

      if (autoscroll is True):
        self.text.AppendText("%s\n" % msg)
      else:
        self.text.Freeze()
        (selection_start, selection_end) = self.text.GetSelection()
        self.text.SetEditable(True)
        self.text.SetInsertionPoint(end_pos)
        self.text.WriteText("%s\n" % msg)
        self.text.SetEditable(False)
        self.text.SetInsertionPoint(current_pos)
        self.text.SetSelection(selection_start, selection_end)
        self.text.Thaw()

    except (Exception) as err:
      sys.stderr.write("Error: %s failed while responding to a log message: %s.\n" % (self.__class__.__name__, err.reason))

    if (e is not None): e.Skip(True)
