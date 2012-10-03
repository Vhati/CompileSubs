from datetime import datetime, timedelta
import logging
import re
import sys
import weakref
import wx
import wx.grid

from lib import common
from lib import snarkutils
from lib.gui import fudgegrid
from lib.gui import vlc


class SnarkFrame(wx.Frame):
  def __init__(self, parent, id, title, snarks_wrapper):
    self.STATUS_FIELDS = ["STATUS_HELP", "STATUS_CORNER"]
    for (i, x) in enumerate(self.STATUS_FIELDS): setattr(self, x, i)

    wx.Frame.__init__(self, parent, id, title=title)
    self._snarks_wrapper = snarks_wrapper
    self._config = snarks_wrapper.clone_config()
    self._snarks = snarks_wrapper.clone_snarks()
    self._grabbed_snark = None
    self.fudge_frame = None
    self._last_video_time = None
    self._last_video_row = None
    self.seek_preroll = 5  # When seeking in video, be N seconds early.

    self.statusbar = self.CreateStatusBar()
    self.statusbar.SetFieldsCount(len(self.STATUS_FIELDS))
    self.statusbar.SetStatusWidths([-1, 17])
    self.statusbar.SetStatusStyles([wx.SB_NORMAL]*1+[wx.SB_FLAT])
    self.SetStatusBar(self.statusbar)
    self._last_status_tip = None
    self.statusbar.SetStatusText("To select a snark, click the row number.", self.STATUS_HELP)

    grid_panel = wx.Panel(self, wx.ID_ANY)
    grid_sizer = wx.BoxSizer(wx.VERTICAL)
    self.snark_grid = wx.grid.Grid(grid_panel, wx.ID_ANY)
    self.snark_table = SnarkGridTable(self.snark_grid, self._config, self._snarks)
    self.snark_grid.SetTable(self.snark_table, True)
    self.snark_grid.SetColSize(self.snark_table.COL_FINAL_TIME, 55)
    self.snark_grid.SetColSize(self.snark_table.COL_USER, 100)
    self.snark_grid.SetColSize(self.snark_table.COL_MSG, 190)
    self.snark_grid.SetColSize(self.snark_table.COL_GLOBALLY_FUDGED_TIME, 55)
    self.snark_grid.SetColSize(self.snark_table.COL_USER_FUDGE, 55)
    self.snark_grid.SetRowLabelSize(35)
    self.snark_grid.DisableDragRowSize()
    self.snark_grid.AutoSizeColumn(self.snark_table.COL_FINAL_TIME)
    self.snark_grid.AutoSizeColumn(self.snark_table.COL_GLOBALLY_FUDGED_TIME)
    self.snark_grid.AutoSizeColumn(self.snark_table.COL_USER_FUDGE)
    grid_sizer.Add(self.snark_grid, 1, flag=wx.EXPAND|wx.BOTTOM, border=10)
    grid_panel.SetSizer(grid_sizer)

    ctrl_panel = wx.Panel(self, wx.ID_ANY)
    ctrl_sizer = wx.BoxSizer(wx.HORIZONTAL)

    self.goto_btn = wx.Button(ctrl_panel, label="Goto", style=wx.BU_EXACTFIT)
    self._shrink_button(self.goto_btn)
    self._set_status_tip(self.goto_btn, "Jump to selected snark's time in the video.")
    self.goto_btn.Bind(wx.EVT_BUTTON, self._on_goto)
    ctrl_sizer.Add(self.goto_btn, flag=wx.ALIGN_CENTER_VERTICAL)

    ctrl_sizer.Add((5,-1))

    user_nav_sizer = wx.BoxSizer(wx.VERTICAL)
    self.prev_user_btn = wx.Button(ctrl_panel, label="User A", style=wx.BU_EXACTFIT)
    self._shrink_button(self.prev_user_btn)
    self._set_status_tip(self.prev_user_btn, "Goto the previous snark from the same user.")
    self.prev_user_btn.Bind(wx.EVT_BUTTON, self._on_prev_user)
    user_nav_sizer.Add(self.prev_user_btn, flag=wx.EXPAND|wx.BOTTOM, border=5)

    self.next_user_btn = wx.Button(ctrl_panel, label="User V", style=wx.BU_EXACTFIT)
    self._shrink_button(self.next_user_btn)
    self._set_status_tip(self.next_user_btn, "Goto the next snark from the same user.")
    self.next_user_btn.Bind(wx.EVT_BUTTON, self._on_next_user)
    user_nav_sizer.Add(self.next_user_btn, flag=wx.EXPAND)
    ctrl_sizer.Add(user_nav_sizer, flag=wx.RIGHT, border=5)

    ctrl_sizer.Add((15,0))

    self.grab_btn = wx.Button(ctrl_panel, label="Grab", style=wx.BU_EXACTFIT)
    self._shrink_button(self.grab_btn)
    self._set_status_tip(self.grab_btn, "Grab selected snark to place at a different time.")
    self.grab_btn.Bind(wx.EVT_BUTTON, self._on_grab_snark)
    ctrl_sizer.Add(self.grab_btn, flag=wx.ALIGN_CENTER_VERTICAL)
    ctrl_sizer.Add((5,-1))
    self.place_btn = wx.Button(ctrl_panel, label="Place", style=wx.BU_EXACTFIT)
    self._shrink_button(self.place_btn)
    self._set_status_tip(self.place_btn, "Place grabbed snark at current time in video.")
    self.place_btn.Enable(False)
    self.place_btn.Bind(wx.EVT_BUTTON, self._on_place_snark)
    ctrl_sizer.Add(self.place_btn, flag=wx.ALIGN_CENTER_VERTICAL)
    ctrl_sizer.Add((5,-1))
    self.drop_btn = wx.Button(ctrl_panel, label="Drop", style=wx.BU_EXACTFIT)
    self._shrink_button(self.drop_btn)
    self._set_status_tip(self.drop_btn, "Drop grabbed snark at its original time.")
    self.drop_btn.Enable(False)
    self.drop_btn.Bind(wx.EVT_BUTTON, self._on_drop_snark)
    ctrl_sizer.Add(self.drop_btn, flag=wx.ALIGN_CENTER_VERTICAL)

    ctrl_sizer.Add((15,0))

    self.edit_fudges_btn = wx.Button(ctrl_panel, label="Fudges...", style=wx.BU_EXACTFIT)
    self._shrink_button(self.edit_fudges_btn)
    self._set_status_tip(self.edit_fudges_btn, "Show all fudges in effect.")
    self.edit_fudges_btn.Bind(wx.EVT_BUTTON, self._on_edit_fudges)
    ctrl_sizer.Add(self.edit_fudges_btn, flag=wx.ALIGN_CENTER_VERTICAL)

    ctrl_panel.SetSizer(ctrl_sizer)

    sizer = wx.BoxSizer(wx.VERTICAL)
    sizer.Add(grid_panel, 1, flag=wx.EXPAND)
    sizer.Add(ctrl_panel, flag=wx.EXPAND|wx.BOTTOM|wx.TOP, border=0)
    self.SetSizer(sizer)

    self.SetSize((450,530))

    self.Bind(wx.EVT_CLOSE, self._on_close)
    self._snarks_wrapper.add_snarks_listener(self)

  def _shrink_button(self, b):
    """Sets a button's preferred size to the average of its current actual and preferred sizes.
    Sizers look at preferred size (which is unaffected by BU_EXACTFIT).
    Call this after setting fonts and before adding to a Sizer.
    This is a fudge for WXMSW; other platforms are unaffected.
    """
    if wx.Platform == "__WXMSW__":
      b.Layout()
      current_size = b.GetSize()
      best_size = b.GetEffectiveMinSize()
      b.SetInitialSize((int((best_size.width+current_size.width)/2), int((best_size.height+current_size.height)/2)))

  def _set_status_tip(self, window, text):
    """Gives gui elements statusbar hover messages."""
    def f(e):
      self._last_status_tip = text
      self.statusbar.SetStatusText(text, self.STATUS_HELP)
      e.Skip(True)
    window.Bind(wx.EVT_ENTER_WINDOW, f)
    window.Bind(wx.EVT_LEAVE_WINDOW, self._trigger_statusbar_clear_tip)

  def on_snarks_changed(self, e):
    """Responds to config/snarks list changes.

    See common.SnarksWrapper.add_snarks_listener().

    :param e: A SnarksEvent.
    """
    config_changed = False
    snarks_changed = False
    if (common.SnarksEvent.FLAG_CONFIG_FUDGES in e.get_flags()):
      config_changed = True
    if (common.SnarksEvent.FLAG_SNARKS in e.get_flags()):
      snarks_changed = True
    if (not config_changed and not snarks_changed): return

    if (self._grabbed_snark is not None): self._on_drop_snark(None)
    if (config_changed): self._config = self._snarks_wrapper.clone_config()
    if (snarks_changed): self._snarks = self._snarks_wrapper.clone_snarks()
    self.snark_table.set_data(self._config, self._snarks)

    if (self._update_video_row() is True):
      self.snark_table.set_video_row(self._last_video_row)
      self.snark_grid.ForceRefresh()

  def _on_goto(self, e):
    """Seeks the video to the currently selected snark row's time."""
    rows = self.snark_grid.GetSelectedRows()
    if (not rows):
      self.statusbar.SetStatusText("No snark selected.", self.STATUS_HELP)
    else:
      wx.GetApp().player_frame.set_vlc_time(max(0, (common.delta_seconds(self._snarks[rows[0]]["time"])-self.seek_preroll) * 1000))

    if (e is not None): e.Skip(False)  # Consume the event.

  def _on_prev_user(self, e):
    """Selects the previous snark row by the currently selected snark's user.
    If possible, the video will seek to the new snark's time.
    """
    rows = self.snark_grid.GetSelectedRows()
    if (not rows):
      self.statusbar.SetStatusText("No snark selected.", self.STATUS_HELP)
    else:
      for i in range(rows[0]-1, -1, -1):
        if (self._snarks[i]["user"] == self._snarks[rows[0]]["user"]):
          self.snark_grid.SelectRow(i, False)
          #self.snark_grid.MakeCellVisible(i, 0)
          cell_bounds = self.snark_grid.CellToRect(i, 0)
          self.snark_grid.Scroll(0, cell_bounds.y // self.snark_grid.GetScrollLineY())
          wx.GetApp().player_frame.set_vlc_time(max(0, (common.delta_seconds(self._snarks[i]["time"])-self.seek_preroll) * 1000))
          break

    if (e is not None): e.Skip(False)  # Consume the event.

  def _on_next_user(self, e):
    """Selects the next snark row by the currently selected snark's user.
    If possible, the video will seek to the new snark's time.
    """
    rows = self.snark_grid.GetSelectedRows()
    if (not rows):
      self.statusbar.SetStatusText("No snark selected.", self.STATUS_HELP)
    else:
      for i in range(rows[0]+1, len(self._snarks)):
        if (self._snarks[i]["user"] == self._snarks[rows[0]]["user"]):
          self.snark_grid.SelectRow(i, False)
          #self.snark_grid.MakeCellVisible(i, 0)
          cell_bounds = self.snark_grid.CellToRect(i, 0)
          self.snark_grid.Scroll(0, cell_bounds.y // self.snark_grid.GetScrollLineY())
          wx.GetApp().player_frame.set_vlc_time(max(0, (common.delta_seconds(self._snarks[i]["time"])-self.seek_preroll) * 1000))
          break

    if (e is not None): e.Skip(False)  # Consume the event.

  def _on_grab_snark(self, e):
    """Chooses the selected snark row for placement later."""
    rows = self.snark_grid.GetSelectedRows()
    if (not rows):
      self.statusbar.SetStatusText("No snark selected.", self.STATUS_HELP)
    else:
      self._grabbed_snark = self._snarks[rows[0]]
      self.grab_btn.Enable(False)
      self.place_btn.Enable(True)
      self.drop_btn.Enable(True)
    if (e is not None): e.Skip(False)  # Consume the event.

  def _on_place_snark(self, e):
    """Adds a new fudge_users value to make the grabbed snark visible at the current video time.
    All config and snarks listeners will be notified of changes.
    """
    if (self._grabbed_snark is None):
      self.statusbar.SetStatusText("Error: No snark was grabbed.", self.STATUS_HELP)
    else:
      vlc_milliseconds = wx.GetApp().player_frame.get_vlc_time()
      if (vlc_milliseconds == -1):
        self.statusbar.SetStatusText("Error: VLC reported a bad time. Aborting placement.", self.STATUS_HELP)
        if (e is not None): e.Skip(False)  # Consume the event.
        return

      grabbed_snark = self._grabbed_snark
      self._grabbed_snark = None
      current_time = timedelta(seconds=(vlc_milliseconds//1000))
      fudge_delta = current_time - grabbed_snark["globally fudged time"]
      fudge_tuple = (grabbed_snark["globally fudged time"], fudge_delta)

      self._snarks_wrapper.checkout(self.__class__.__name__)
      snarkutils.config_add_user_fudge(self._snarks_wrapper.get_config(), grabbed_snark["user"], fudge_tuple)
      snarkutils.gui_fudge_users(self._snarks_wrapper.get_config(), self._snarks_wrapper.get_snarks())
      self._snarks_wrapper.commit()

      new_event = common.SnarksEvent([common.SnarksEvent.FLAG_CONFIG_FUDGES, common.SnarksEvent.FLAG_SNARKS])
      self._snarks_wrapper.fire_snarks_event(new_event)

      # Reselect the grabbed snark.
      for i in range(len(self._snarks)):
        snark = self._snarks[i]
        if (snark["user"] == grabbed_snark["user"] and snark["date"] == grabbed_snark["date"]):
          self.snark_grid.SelectRow(i, False)
          break

    self.grab_btn.Enable(True)
    self.place_btn.Enable(False)
    self.drop_btn.Enable(False)
    if (e is not None): e.Skip(False)  # Consume the event.

  def _on_drop_snark(self, e):
    """Cancels placement of a grabbed snark."""
    self._grabbed_snark = None
    self.grab_btn.Enable(True)
    self.place_btn.Enable(False)
    self.drop_btn.Enable(False)
    if (e is not None): e.Skip(False)  # Consume the event.

  def _on_edit_fudges(self, e):
    """Shows the fudges window."""
    self.edit_fudges_btn.Enable(False)
    self.fudge_frame = fudgegrid.FudgeFrame(self, wx.ID_ANY, "Fudges", self._snarks_wrapper)
    self.fudge_frame.Show()
    self.fudge_frame.Bind(wx.EVT_WINDOW_DESTROY, self._on_fudge_frame_destroyed)
    if (e is not None): e.Skip(False)  # Consume the event.

  def _trigger_statusbar_clear(self, e):
    self.statusbar.SetStatusText("", self.STATUS_HELP)
    if (e is not None): e.Skip(True)

  def _trigger_statusbar_clear_tip(self, e):
    """Clears the statusbar's help, only if its text was from hovering."""
    if (self._last_status_tip and self._last_status_tip == self.statusbar.GetStatusText()):
      self._trigger_statusbar_clear(None)
    self._last_status_tip = None
    if (e is not None): e.Skip(True)

  def set_video_time(self, milliseconds):
    """Notifies this widget that the video time has changed."""
    seconds = milliseconds // 1000
    if (self._last_video_time is None or seconds != self._last_video_time):
      self._last_video_time = seconds
      if (self._update_video_row() is True):
        self.snark_table.set_video_row(self._last_video_row)
        self.snark_grid.ForceRefresh()

        # If within the duration of a snark's show time, display it.
        last_video_snark = self._snarks[self._last_video_row]
        if (abs(common.delta_seconds(last_video_snark["time"]) - seconds) <= common.delta_seconds(self._config.show_time)):
          # Back up a bit to collate simultaneous snarks.
          msgs = []
          for i in range(self._last_video_row, -1, -1):
            snark = self._snarks[i]
            if (snark["time"] != last_video_snark["time"]): break
            msgs.insert(0, "%s: %s" % (snark["user"], snark["msg"]))
          msg = "\n".join(msgs)
          if (len(msg) > 0):
            wx.GetApp().player_frame.show_vlc_message(msg)

  def _update_video_row(self):
    """Determines the most recent row number, relative to video time.

    :returns: True if the row has changed, False otherwise.
    """
    if (self._last_video_time is None):
      if (self._last_video_row is not None):
        self._last_video_row = None
        return True
      else:
        return False

    result = None
    start_row = 0
    if (self._last_video_row is not None):
      # Take a shortcut: Scan from where we used to be.
      if (common.delta_seconds(self._snarks[self._last_video_row]["time"]) < self._last_video_time):
        start_row = self._last_video_row

    for i in range(start_row, len(self._snarks)-1):
      snark = self._snarks[i]
      if (common.delta_seconds(snark["time"]) <= self._last_video_time):
        next_snark = self._snarks[i+1]
        if (common.delta_seconds(next_snark["time"]) > self._last_video_time):
          result = i
          break
    if (result != self._last_video_row):
      self._last_video_row = result
      return True
    else:
      return False

  def _on_fudge_frame_destroyed(self, e):
    self.fudge_frame = None
    self.edit_fudges_btn.Enable(True)
    if (e is not None): e.Skip(True)

  def _on_close(self, e):
    self._snarks_wrapper.remove_snarks_listener(self)
    if (self.fudge_frame is not None): self.fudge_frame.Close()
    self.Destroy()
    if (e is not None): e.Skip(False)  # Consume the event.


class SnarkGridTable(wx.grid.PyGridTableBase):
  def __init__(self, gridview, config, snarks):
    wx.grid.PyGridTableBase.__init__(self)
    cols = [("COL_FINAL_TIME", "Final\nTime"),
                 ("COL_USER", "User"),
                 ("COL_MSG", "Msg"),
                 ("COL_GLOBALLY_FUDGED_TIME", "Globally\nFudged"),
                 ("COL_USER_FUDGE", "User\nFudge")
                 ]
    self._col_labels = []
    for (n,(enum,name)) in enumerate(cols):
      setattr(self, enum, n)
      self._col_labels.append(name)

    self._col_attrs = {}
    # Set right-aligned column attrs.
    for col in [self.COL_FINAL_TIME,self.COL_GLOBALLY_FUDGED_TIME,self.COL_USER_FUDGE]:
      attr = wx.grid.GridCellAttr()
      attr.SetAlignment(wx.ALIGN_RIGHT,wx.ALIGN_CENTRE)
      self._col_attrs[col] = attr
    # Set default attrs on remaining columns.
    for col in range(len(cols)):
      if (col not in self._col_attrs):
        attr = wx.grid.GridCellAttr()
        self._col_attrs[col] = attr

    self._gridref = weakref.ref(gridview)  # Can't rely on GetView().
    self._config = config
    self._snarks = snarks
    self._last_video_row = None

  def GetNumberRows(self):
    return len(self._snarks)

  def GetNumberCols(self):
    return len(self._col_labels)

  def IsEmptyCell(self, row, col):
    return False

  def GetValue(self, row, col):
    snark = self._snarks[row]

    if (col == self.COL_FINAL_TIME):
      return common.delta_str(snark["time"])
    elif (col == self.COL_USER):
      return snark["user"]
    elif (col == self.COL_MSG):
      return snark["msg"]
    elif (col == self.COL_GLOBALLY_FUDGED_TIME):
      return common.delta_str(snark["globally fudged time"])
    elif (col == self.COL_USER_FUDGE):
      # Search backward through a user's delays for one in the recent past.
      if (snark["user"] in self._config.fudge_users):
        for (bookmark, fudge_value) in reversed(self._config.fudge_users[snark["user"]]):
          if (snark["globally fudged time"] >= bookmark):
            return common.delta_str(fudge_value)
        return common.delta_str(timedelta(0))
      else:
        return common.delta_str(timedelta(0))
    else:
      return "(%s,%s)" % (row, col)

  def SetValue(self, row, col, value):
    pass

  def GetAttr(self, row, col, kind):
    attr = None
    if (col in self._col_attrs):
      attr = self._col_attrs[col]
      attr.IncRef()
    else:
      attr = wx.grid.GridCellAttr()

    if (self._last_video_row is not None and row == self._last_video_row):
      # Highlight the most recent snark according to video time.
      new_attr = attr.Clone()
      attr.DecRef()
      new_attr.SetBackgroundColour(wx.Colour(220, 220, 220, 255))
      attr = new_attr

    return attr

  def GetColLabelValue(self, col):
    return self._col_labels[col]

  def GetRowLabelValue(self, row):
    return str(row)

  def set_video_row(self, row):
    """Sets the row of the most recently visible snark."""
    self._last_video_row = row

  def set_data(self, config, snarks):
    """Replaces the backend config and/or snarks list.

    :param config: A read-only config, or None to retain the current one.
    :param snarks: A read-only snarks list, or None to retain the current one.
    """
    gridview = self._gridref()
    if (gridview is not None and gridview.GetTable() is not self):
      gridview = None

    if (gridview is not None): gridview.BeginBatch()
    grid_msg = wx.grid.GridTableMessage(self, wx.grid.GRIDTABLE_NOTIFY_ROWS_DELETED, 0, len(self._snarks))
    self._snarks = []
    if (gridview is not None): gridview.ProcessTableMessage(grid_msg)

    if (config is not None): self._config = config
    if (snarks is not None): self._snarks = snarks
    grid_msg = wx.grid.GridTableMessage(self, wx.grid.GRIDTABLE_NOTIFY_ROWS_APPENDED, len(self._snarks))
    if (gridview is not None): gridview.ProcessTableMessage(grid_msg)
    if (gridview is not None): gridview.EndBatch()
