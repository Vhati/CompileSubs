import logging
import os
import platform
import re
import sys
import wx

from lib import common
from lib import global_config
from lib import snarkutils


class PaletteFrame(wx.Frame):
  def __init__(self, parent, id, title):
    wx.Frame.__init__(self, parent, id, title=title)

    self._swatches = []

    self._pane = wx.Panel(self, wx.ID_ANY)

    swatch_sizer = wx.GridSizer(rows=0, cols=6, vgap=5, hgap=5)
    for c in snarkutils.get_color_library():
      swatch = ColorSwatch(self._pane, wx.ID_ANY)
      swatch.set_swatch_color(c["hex"])
      swatch.set_selected(c["use"])
      swatch.SetToolTipString(c["hex"])
      swatch_sizer.Add(swatch, flag=wx.ALIGN_CENTER)
      self._swatches.append(swatch)

    self.ok_btn = wx.Button(self._pane, wx.ID_ANY, label="OK")
    self.ok_btn.Bind(wx.EVT_BUTTON, self._on_ok)

    ctrl_sizer = wx.BoxSizer(wx.HORIZONTAL)
    ctrl_sizer.Add((-1, 1), 1)
    ctrl_sizer.Add(self.ok_btn)
    ctrl_sizer.Add((-1, 1), 1)

    self._pane_sizer = wx.BoxSizer(wx.VERTICAL)
    self._pane_sizer.Add(swatch_sizer, flag=wx.ALIGN_CENTER_HORIZONTAL)
    self._pane_sizer.Add((-1, 8), 0, flag=wx.EXPAND)
    self._pane_sizer.Add(ctrl_sizer, 0, flag=wx.EXPAND)
    self._pane.SetSizer(self._pane_sizer)

    sizer = wx.BoxSizer(wx.VERTICAL)
    sizer.Add(self._pane, 1, flag=wx.EXPAND)
    self.SetSizer(sizer)

    #self.SetSize((325,200))
    self.Fit()

    self.Bind(wx.EVT_CLOSE, self._on_close)

  def _on_ok(self, e):
    colors = snarkutils.get_color_library()
    for s in self._swatches:
      for c in colors:
        if (s.get_swatch_color() == c["hex"]):
          c["use"] = s.is_selected()
          break
    snarkutils.set_color_library(colors)
    self.Close()
    if (e is not None): e.Skip(False)  # Consume the event.

  def _on_close(self, e):
    self.Destroy()
    if (e is not None): e.Skip(False)  # Consume the event.


class ColorSwatch(wx.Panel):
  def __init__(self, parent, id):
    wx.Panel.__init__(self, parent, id, size=(30, 30), style=wx.SUNKEN_BORDER)
    self.parent = parent

    self._swatch_color = "#FFCCB8"
    self._selected_state = False
    self.Bind(wx.EVT_LEFT_UP, self._on_click)
    self.Bind(wx.EVT_PAINT, self._on_paint)
    self.Bind(wx.EVT_SIZE, self._on_size)

  def set_swatch_color(self, rgb_hex_str):
    if (self._swatch_color[1:] == rgb_hex_str.upper()): return
    self._swatch_color = "#"+ rgb_hex_str.upper()
    self.Refresh()

  def get_swatch_color(self):
    """Returns the swatch's hex color string."""
    return self._swatch_color[1:]

  def set_selected(self, b):
    if (self._selected_state == bool(b)): return
    self._selected_state = bool(b)
    self.Refresh()

  def is_selected(self):
    return self._selected_state

  def _on_click(self, e):
    self.set_selected(not self.is_selected())
    if (e): e.Skip(False)  # Consume the event.

  def _on_paint(self, e):
    dc = wx.PaintDC(self)
    w, h = dc.GetSize()
    margin = 6

    dc.SetPen(wx.Pen("#a4a4a4"))
    dc.SetBrush(wx.Brush("#a4a4a4"))
    dc.DrawPolygon([wx.Point(0,0), wx.Point(w-1,0), wx.Point(0,h-1)])

    dc.SetPen(wx.Pen("#000000"))
    dc.SetBrush(wx.Brush("#000000"))
    dc.DrawPolygon([wx.Point(w-1,0), wx.Point(w-1,h-1), wx.Point(0,h-1)])

    if (self.is_selected()):
      dc.SetPen(wx.Pen("#00cc00", width=5))
    else:
      dc.SetPen(wx.Pen("#cc0000", width=5))
    dc.DrawLines([wx.Point(w-1,0), wx.Point(0,h-1)])

    dc.SetPen(wx.Pen("#5C5142"))
    dc.SetBrush(wx.Brush(self._swatch_color))
    dc.DrawRectangle(margin, margin, w-margin*2, h-margin*2)

  def _on_size(self, e):
    self.Refresh()
