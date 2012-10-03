from datetime import datetime, timedelta
import logging
import re
import sys
import weakref
import wx
import wx.grid

from lib import common
from lib import snarkutils
from lib.gui import vlc


class FudgeFrame(wx.Frame):
  def __init__(self, parent, id, title, snarks_wrapper):
    self.STATUS_FIELDS = ["STATUS_HELP", "STATUS_CORNER"]
    for (i, x) in enumerate(self.STATUS_FIELDS): setattr(self, x, i)

    wx.Frame.__init__(self, parent, id, title=title)
    self._snarks_wrapper = snarks_wrapper
    self._config = snarks_wrapper.clone_config()

    self.statusbar = self.CreateStatusBar()
    self.statusbar.SetFieldsCount(len(self.STATUS_FIELDS))
    self.statusbar.SetStatusWidths([-1, 17])
    self.statusbar.SetStatusStyles([wx.SB_NORMAL]*1+[wx.SB_FLAT])
    self.SetStatusBar(self.statusbar)
    self._last_status_tip = None
    self.statusbar.SetStatusText("To select a fudge, click the row number.", self.STATUS_HELP)

    self._pane = wx.Panel(self, wx.ID_ANY)

    grid_panel = wx.Panel(self._pane, wx.ID_ANY)
    grid_sizer = wx.BoxSizer(wx.VERTICAL)
    self.fudge_grid = wx.grid.Grid(grid_panel, wx.ID_ANY)
    self.fudge_table = FudgeGridTable(self.fudge_grid, self._config)
    self.fudge_grid.SetTable(self.fudge_table, True)
    self.fudge_grid.SetColSize(self.fudge_table.COL_USER, 100)
    self.fudge_grid.SetColSize(self.fudge_table.COL_GLOBALLY_FUDGED_TIME, 55)
    self.fudge_grid.SetColSize(self.fudge_table.COL_USER_FUDGE, 55)
    self.fudge_grid.SetRowLabelSize(35)
    self.fudge_grid.DisableDragRowSize()
    self.fudge_grid.AutoSizeColumn(self.fudge_table.COL_GLOBALLY_FUDGED_TIME)
    self.fudge_grid.AutoSizeColumn(self.fudge_table.COL_USER_FUDGE)
    grid_sizer.Add(self.fudge_grid, 1, flag=wx.EXPAND|wx.BOTTOM, border=10)
    grid_panel.SetSizer(grid_sizer)

    ctrl_panel = wx.Panel(self._pane, wx.ID_ANY)
    ctrl_sizer = wx.BoxSizer(wx.HORIZONTAL)

    self._new_btn = wx.Button(ctrl_panel, label="New", style=wx.BU_EXACTFIT)
    self._shrink_button(self._new_btn)
    self._set_status_tip(self._new_btn, "Create a new fudge, copying values from selection, if any.")
    self._new_btn.Bind(wx.EVT_BUTTON, self._on_new)
    ctrl_sizer.Add(self._new_btn, flag=wx.ALIGN_CENTER_VERTICAL)
    ctrl_sizer.Add((5,-1))
    self._edit_btn = wx.Button(ctrl_panel, label="Edit", style=wx.BU_EXACTFIT)
    self._shrink_button(self._edit_btn)
    self._set_status_tip(self._edit_btn, "Edit selected fudge.")
    self._edit_btn.Bind(wx.EVT_BUTTON, self._on_edit)
    ctrl_sizer.Add(self._edit_btn, flag=wx.ALIGN_CENTER_VERTICAL)
    ctrl_sizer.Add((5,-1))
    self._delete_btn = wx.Button(ctrl_panel, label="Delete", style=wx.BU_EXACTFIT)
    self._shrink_button(self._delete_btn)
    self._set_status_tip(self._delete_btn, "Delete selected fudge.")
    self._delete_btn.Bind(wx.EVT_BUTTON, self._on_delete)
    ctrl_sizer.Add(self._delete_btn, flag=wx.ALIGN_CENTER_VERTICAL)

    ctrl_panel.SetSizer(ctrl_sizer)

    self._edit_panel = wx.Panel(self._pane, wx.ID_ANY)
    edit_sizer = wx.BoxSizer(wx.VERTICAL)

    self._edit_status_label = wx.StaticText(self._edit_panel, wx.ID_ANY, label="- - -")
    edit_sizer.Add(self._edit_status_label, flag=wx.LEFT|wx.BOTTOM, border=4)

    edit_fields_sizer = wx.BoxSizer(wx.HORIZONTAL)

    self._edit_user_field = wx.TextCtrl(self._edit_panel, wx.ID_ANY, value="@Someone")
    edit_fields_sizer.Add(self._edit_user_field)

    self._edit_bookmark_field = wx.TextCtrl(self._edit_panel, wx.ID_ANY, value="00:00:00")
    edit_fields_sizer.Add(self._edit_bookmark_field)

    self._edit_fudge_field = wx.TextCtrl(self._edit_panel, wx.ID_ANY, value="00:00:00")
    edit_fields_sizer.Add(self._edit_fudge_field)

    edit_sizer.Add(edit_fields_sizer)
    edit_sizer.Add((-1,5))
    edit_ctrl_sizer = wx.BoxSizer(wx.HORIZONTAL)

    self._edit_cancel_btn = wx.Button(self._edit_panel, label="Cancel", style=wx.BU_EXACTFIT)
    self._shrink_button(self._edit_cancel_btn)
    self._set_status_tip(self._edit_cancel_btn, "Cancel changes.")
    self._edit_cancel_btn.Bind(wx.EVT_BUTTON, self._on_edit_cancel)
    edit_ctrl_sizer.Add(self._edit_cancel_btn, flag=wx.ALIGN_CENTER_VERTICAL)
    edit_ctrl_sizer.Add((5,-1))
    self._edit_ok_btn = wx.Button(self._edit_panel, label="OK", style=wx.BU_EXACTFIT)
    self._shrink_button(self._edit_ok_btn)
    self._set_status_tip(self._edit_ok_btn, "Commit changes.")
    self._edit_ok_btn.Bind(wx.EVT_BUTTON, self._on_edit_ok)
    edit_ctrl_sizer.Add(self._edit_ok_btn, flag=wx.ALIGN_CENTER_VERTICAL)

    edit_sizer.Add(edit_ctrl_sizer, flag=wx.ALIGN_RIGHT)

    self._edit_panel.SetSizer(edit_sizer)

    self._pane_sizer = wx.BoxSizer(wx.VERTICAL)
    self._pane_sizer.Add(grid_panel, 1, flag=wx.EXPAND)
    self._pane_sizer.Add(ctrl_panel, flag=wx.EXPAND|wx.BOTTOM|wx.TOP, border=0)

    sep_line = wx.StaticLine(self._pane, wx.ID_ANY)
    self._pane_sizer.Add(sep_line, flag=wx.EXPAND|wx.ALIGN_CENTER_VERTICAL|wx.BOTTOM|wx.TOP, border=15)

    self._pane_sizer.Add(self._edit_panel)
    self._pane_sizer.Add((-1,10))
    self._pane.SetSizer(self._pane_sizer)

    sizer = wx.BoxSizer(wx.VERTICAL)
    sizer.Add(self._pane, 1, flag=wx.EXPAND)
    self.SetSizer(sizer)

    self.SetSize((325,400))

    self._on_edit_cancel(None)
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
    if (common.SnarksEvent.FLAG_CONFIG_FUDGES not in e.get_flags()):
      return

    if (self._edited_row is not None): self._on_edit_cancel(None)
    self._config = self._snarks_wrapper.clone_config()
    self.fudge_table.set_data(self._config)

  def _trigger_statusbar_clear(self, e):
    self.statusbar.SetStatusText("", self.STATUS_HELP)
    if (e is not None): e.Skip(True)

  def _trigger_statusbar_clear_tip(self, e):
    """Clears the statusbar's help, only if its text was from hovering."""
    if (self._last_status_tip and self._last_status_tip == self.statusbar.GetStatusText()):
      self._trigger_statusbar_clear(None)
    self._last_status_tip = None
    if (e is not None): e.Skip(True)

  def _on_new(self, e):
    """Begins editing a new fudge.
    If a fudge row was selected, its values will be copied.
    """
    default_user = "@"
    default_bookmark = "00:00:00"
    default_fudge = "00:00:00"

    rows = self.fudge_grid.GetSelectedRows()
    if (rows):
      default_user = self.fudge_table.GetValue(rows[0], self.fudge_table.COL_USER)
      default_bookmark = self.fudge_table.GetValue(rows[0], self.fudge_table.COL_GLOBALLY_FUDGED_TIME)
      default_fudge = self.fudge_table.GetValue(rows[0], self.fudge_table.COL_USER_FUDGE)

    self._edited_row = -1
    self._edit_status_label.SetLabel("New...")
    self._edit_user_field.SetValue(default_user)
    self._edit_bookmark_field.SetValue(default_bookmark)
    self._edit_fudge_field.SetValue(default_fudge)
    self._edit_panel.Enable(True)
    if (e is not None): e.Skip(False)  # Consume the event.

  def _on_edit(self, e):
    rows = self.fudge_grid.GetSelectedRows()
    if (not rows):
      self.statusbar.SetStatusText("No fudge selected.", self.STATUS_HELP)
    else:
      self._edited_row = rows[0]
      default_user = self.fudge_table.GetValue(rows[0], self.fudge_table.COL_USER)
      default_bookmark = self.fudge_table.GetValue(rows[0], self.fudge_table.COL_GLOBALLY_FUDGED_TIME)
      default_fudge = self.fudge_table.GetValue(rows[0], self.fudge_table.COL_USER_FUDGE)

      self._edit_status_label.SetLabel("Editing #%d..." % self._edited_row)
      self._edit_user_field.SetValue(default_user)
      self._edit_bookmark_field.SetValue(default_bookmark)
      self._edit_fudge_field.SetValue(default_fudge)
      self._edit_panel.Enable(True)
    if (e is not None): e.Skip(False)  # Consume the event.

  def _on_delete(self, e):
    rows = self.fudge_grid.GetSelectedRows()
    if (not rows):
      self.statusbar.SetStatusText("No fudge selected.", self.STATUS_HELP)
    else:
      self._snarks_wrapper.checkout(self.__class__.__name__)
      config = self._snarks_wrapper.get_config()

      doomed_user = self.fudge_table.GetValue(rows[0], self.fudge_table.COL_USER)
      doomed_bookmark = common.delta_from_str(self.fudge_table.GetValue(rows[0], self.fudge_table.COL_GLOBALLY_FUDGED_TIME))
      snarkutils.config_remove_user_fudge(config, doomed_user, doomed_bookmark)

      snarkutils.gui_fudge_users(config, self._snarks_wrapper.get_snarks())
      self._snarks_wrapper.commit()

      new_event = common.SnarksEvent([common.SnarksEvent.FLAG_CONFIG_FUDGES, common.SnarksEvent.FLAG_SNARKS])
      self._snarks_wrapper.fire_snarks_event(new_event)

    if (e is not None): e.Skip(False)  # Consume the event.

  def _on_edit_cancel(self, e):
    self._edit_panel.Enable(False)
    self._edit_status_label.SetLabel("- - -")
    self._edit_user_field.SetValue("@Someone")
    self._edit_bookmark_field.SetValue("00:00:00")
    self._edit_fudge_field.SetValue("00:00:00")
    self._edited_row = None
    if (e is not None): e.Skip(False)  # Consume the event.

  def _on_edit_ok(self, e):
    assert (self._edited_row is not None)

    user, bookmark, fudge_amount = None, None, None

    user = self._edit_user_field.GetValue()
    if (len(user) == 0 or user == "@"): user = None
    bookmark = common.delta_from_str(self._edit_bookmark_field.GetValue())
    fudge_amount = common.delta_from_str(self._edit_fudge_field.GetValue())

    proceed = True
    for x,noun in [(user, "user"), (bookmark, "time"), (fudge_amount, "fudge amount")]:
      if (x is None):
        self.statusbar.SetStatusText("Error: Bad %s." % noun, self.STATUS_HELP)
        proceed = False
        break

    if (proceed is True):
      self._snarks_wrapper.checkout(self.__class__.__name__)
      config = self._snarks_wrapper.get_config()
      if (self._edited_row != -1):
        # Remove the old user fudge that had been edited.
        doomed_user = self.fudge_table.GetValue(self._edited_row, self.fudge_table.COL_USER)
        doomed_bookmark = common.delta_from_str(self.fudge_table.GetValue(self._edited_row, self.fudge_table.COL_GLOBALLY_FUDGED_TIME))
        snarkutils.config_remove_user_fudge(config, doomed_user, doomed_bookmark)

      snarkutils.config_add_user_fudge(config, user, (bookmark, fudge_amount))
      snarkutils.gui_fudge_users(config, self._snarks_wrapper.get_snarks())
      self._snarks_wrapper.commit()

      new_event = common.SnarksEvent([common.SnarksEvent.FLAG_CONFIG_FUDGES, common.SnarksEvent.FLAG_SNARKS])
      self._snarks_wrapper.fire_snarks_event(new_event)

      self._on_edit_cancel(None)

    if (e is not None): e.Skip(False)  # Consume the event.

  def _on_close(self, e):
    self._snarks_wrapper.remove_snarks_listener(self)
    self.Destroy()
    if (e is not None): e.Skip(False)  # Consume the event.


class FudgeGridTable(wx.grid.PyGridTableBase):
  def __init__(self, gridview, config):
    wx.grid.PyGridTableBase.__init__(self)
    cols = [("COL_USER", "User"),
            ("COL_GLOBALLY_FUDGED_TIME", "Globally\nFudged"),
            ("COL_USER_FUDGE", "User\nFudge")
            ]
    self._col_labels = []
    for (n,(enum,name)) in enumerate(cols):
      setattr(self, enum, n)
      self._col_labels.append(name)

    self._col_attrs = {}
    # Set right-aligned column attrs.
    for col in [self.COL_GLOBALLY_FUDGED_TIME,self.COL_USER_FUDGE]:
      attr = wx.grid.GridCellAttr()
      attr.SetReadOnly(True)
      attr.SetAlignment(wx.ALIGN_RIGHT,wx.ALIGN_CENTRE)
      self._col_attrs[col] = attr
    # Set default attrs on remaining columns.
    for col in range(len(cols)):
      if (col not in self._col_attrs):
        attr = wx.grid.GridCellAttr()
        attr.SetReadOnly(True)
        self._col_attrs[col] = attr

    self._gridref = weakref.ref(gridview)  # Can't rely on GetView().
    self._config = None
    self._data = []
    self.set_data(config)

  def GetNumberRows(self):
    return len(self._data)

  def GetNumberCols(self):
    return len(self._col_labels)

  def IsEmptyCell(self, row, col):
    return False

  def GetValue(self, row, col):
    if (col == self.COL_USER):
      return self._data[row]["user"]
    elif (col == self.COL_GLOBALLY_FUDGED_TIME):
      return common.delta_str(self._data[row]["bookmark"])
    elif (col == self.COL_USER_FUDGE):
      return common.delta_str(self._data[row]["fudge"])
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

    return attr

  def GetColLabelValue(self, col):
    return self._col_labels[col]

  def GetRowLabelValue(self, row):
    return str(row)

  def set_data(self, config):
    """Replaces the backend config.

    :param config: A read-only config, or None to retain the current one.
    """
    gridview = self._gridref()
    if (gridview is not None and gridview.GetTable() is not self):
      gridview = None

    if (gridview is not None): gridview.BeginBatch()
    grid_msg = wx.grid.GridTableMessage(self, wx.grid.GRIDTABLE_NOTIFY_ROWS_DELETED, 0, len(self._data))
    self._config = None
    self._data = []
    if (gridview is not None): gridview.ProcessTableMessage(grid_msg)

    self._config = config
    for user in sorted(self._config.fudge_users.keys(), key=lambda x: x.lower()):
      for fudge_tuple in self._config.fudge_users[user]:
        self._data.append({"user":user, "bookmark":fudge_tuple[0], "fudge":fudge_tuple[1]})

    grid_msg = wx.grid.GridTableMessage(self, wx.grid.GRIDTABLE_NOTIFY_ROWS_APPENDED, len(self._data))
    if (gridview is not None): gridview.ProcessTableMessage(grid_msg)
    if (gridview is not None): gridview.EndBatch()
