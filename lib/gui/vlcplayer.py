# Based on wxvlc.py (23-11-2010)

# http://liris.cnrs.fr/advene/download/python-ctypes/doc/

# Other implementations.
# https://github.com/freevo/kaa-popcorn/blob/master/test/vlc/child.py
# http://svn.tribler.org/abc/branches/yathi/BittBlogg/Tribler/Video/EmbeddedPlayer.py

from datetime import datetime, timedelta
import logging
import os
import platform
import Queue
import re
import sys
import wx
import wx.grid

from lib import common
from lib import global_config
from lib import snarkutils
from lib.gui import snarkgrid
from lib.gui import vlc


class PlayerFrame(wx.Frame):
  def __init__(self, parent, id, title, snarks_wrapper):
    wx.Frame.__init__(self, parent, id, title=title)
    self.STATUS_FIELDS = ["STATUS_HELP",
                          "STATUS_CLOCK", "STATUS_LENGTH", "STATUS_CORNER"]
    for (i, x) in enumerate(self.STATUS_FIELDS): setattr(self, x, i)

    # Menuitems.
    self.ID_FILE_OPEN = wx.ID_OPEN
    self.ID_FILE_SNARKS = wx.NewId()
    self.ID_FILE_EXPORT = wx.NewId()
    self.ID_FILE_EXIT = wx.ID_EXIT

    self._snarks_wrapper = snarks_wrapper
    self._config = self._snarks_wrapper.clone_config()
    self._last_video_time = None
    self.snark_frame = None

    self.vlc_obj = None
    self.vlc_player = None
    self.vlc_event_manager = None

    menubar = wx.MenuBar()

    file_menu = wx.Menu()
    open_menuitem = file_menu.Append(self.ID_FILE_OPEN, "&Open Video...\tCtrl-O")
    self.Bind(wx.EVT_MENU, self._on_open, open_menuitem)
    file_menu.AppendSeparator()
    self.snarks_menuitem = file_menu.Append(self.ID_FILE_SNARKS, "&Snarks...")
    self.Bind(wx.EVT_MENU, self._on_show_snarks, self.snarks_menuitem)
    export_menuitem = file_menu.Append(self.ID_FILE_EXPORT, "&Export Snarks")
    self.Bind(wx.EVT_MENU, self._on_export, export_menuitem)
    file_menu.AppendSeparator()
    exit_menuitem = file_menu.Append(self.ID_FILE_EXIT, "E&xit\tAlt-X")
    self.Bind(wx.EVT_MENU, self._on_close, exit_menuitem)
    menubar.Append(file_menu, "&File")

    self.SetMenuBar(menubar)

    self.statusbar = self.CreateStatusBar()
    self.statusbar.SetFieldsCount(len(self.STATUS_FIELDS))
    self.statusbar.SetStatusWidths([-1, 60, 60, 17])  # 45
    self.statusbar.SetStatusStyles([wx.SB_NORMAL]*3+[wx.SB_FLAT])
    self.SetStatusBar(self.statusbar)
    self._last_status_tip = None

    # Create a black placeholder panel for the video overlay.
    self.video_panel = wx.Panel(self, wx.ID_ANY)
    self.video_panel.SetBackgroundColour(wx.BLACK)

    self.ctrl_panel = wx.Panel(self, wx.ID_ANY)

    timenav_sizer = wx.BoxSizer(wx.HORIZONTAL)
    self.timeslider = wx.Slider(self.ctrl_panel, wx.ID_ANY, 0, 0, 1000)
    self.timeslider.SetLineSize(0)  # Nerf tiny cursor key scrubbing.
    self.timeslider.Enable(False)
    # EVT_SCROLL fires often without signalling release.
    # Events that do aren't cross platform. :/
    self.timeslider.Bind(wx.EVT_LEFT_DOWN, self._on_scrub_start)
    self.timeslider.Bind(wx.EVT_LEFT_UP, self._on_scrub_end)
    self.timeslider.Bind(wx.EVT_LEAVE_WINDOW, self._on_scrub_end)
    # PAGEUP/PAGEDOWN are large jumps from clicking to the side (LEFT_UP catches those).
    timenav_sizer.Add(self.timeslider, 1, flag=wx.TOP|wx.BOTTOM, border=5)

    playback_font = wx.Font(11, wx.FONTFAMILY_DEFAULT, wx.NORMAL, wx.FONTWEIGHT_BOLD)
    playback_sizer = wx.BoxSizer(wx.HORIZONTAL)

    self.play_btn = wx.Button(self.ctrl_panel, label="Play", style=wx.BU_EXACTFIT)
    #self.play_btn.SetFont(playback_font)
    self._shrink_button(self.play_btn)
    self._set_status_tip(self.play_btn, "Play")
    self.play_btn.Bind(wx.EVT_BUTTON, self._on_play)
    playback_sizer.Add(self.play_btn)

    self.pause_btn = wx.Button(self.ctrl_panel, label="Pause", style=wx.BU_EXACTFIT)
    #self.pause_btn.SetFont(playback_font)
    self._shrink_button(self.pause_btn)
    self._set_status_tip(self.pause_btn, "Pause")
    self.pause_btn.Show(False)
    self.pause_btn.Bind(wx.EVT_BUTTON, self._on_pause)
    playback_sizer.Add(self.pause_btn)

    playback_sizer.Add((5,-1))

    self.stop_btn = wx.Button(self.ctrl_panel, label="Stop", style=wx.BU_EXACTFIT)
    #self.stop_btn.SetFont(playback_font)
    self._shrink_button(self.stop_btn)
    self._set_status_tip(self.stop_btn, "Stop")
    self.stop_btn.Bind(wx.EVT_BUTTON, self._on_stop)
    playback_sizer.Add(self.stop_btn)

    playback_sizer.Add((20,0))

    self.seek_minus_ten_btn = wx.Button(self.ctrl_panel, label="-10s", style=wx.BU_EXACTFIT)
    self._shrink_button(self.seek_minus_ten_btn)
    self._set_status_tip(self.seek_minus_ten_btn, "Seek backward 10 seconds.")
    self.seek_minus_ten_btn.Bind(wx.EVT_BUTTON, self._on_seek_minus_ten)
    playback_sizer.Add(self.seek_minus_ten_btn)
    playback_sizer.Add((5,-1))
    self.seek_plus_ten_btn = wx.Button(self.ctrl_panel, label="+10s", style=wx.BU_EXACTFIT)
    self._shrink_button(self.seek_plus_ten_btn)
    self._set_status_tip(self.seek_plus_ten_btn, "Seek forward 10 seconds.")
    self.seek_plus_ten_btn.Bind(wx.EVT_BUTTON, self._on_seek_plus_ten)
    playback_sizer.Add(self.seek_plus_ten_btn)

    playback_sizer.Add((-1,-1), 1)
    self.volslider = wx.Slider(self.ctrl_panel, wx.ID_ANY, 50, 0, 100, size=(100, -1))
    self.volslider.Bind(wx.EVT_SLIDER, self._on_adj_volume)
    playback_sizer.Add(self.volslider)

    ctrl_sizer = wx.BoxSizer(wx.VERTICAL)
    ctrl_sizer.Add(timenav_sizer, flag=wx.EXPAND)
    ctrl_sizer.Add(playback_sizer, 1, wx.EXPAND)
    self.ctrl_panel.SetSizer(ctrl_sizer)

    sizer = wx.BoxSizer(wx.VERTICAL)
    sizer.Add(self.video_panel, 1, flag=wx.EXPAND)
    playback_sizer.Add((-1,10))
    sizer.Add(self.ctrl_panel, flag=wx.EXPAND|wx.BOTTOM|wx.TOP, border=0)
    self.SetSizer(sizer)
    self.SetMinSize((670,568))

    ##self.SetSize(670,568)
    #self.SetClientSize(main_panel.GetBestSize())
    ##self.Fit()

    self.Bind(wx.EVT_CLOSE, self._on_close)
    self.Bind(wx.EVT_WINDOW_DESTROY, self._on_destroy)

    # Slave the GUI to VLC's status.
    self.pulse_timer = wx.Timer(self)
    self.Bind(wx.EVT_TIMER, self._on_pulse, self.pulse_timer)

    self.scrubbing = False
    self.new_volume = self.volslider.GetValue()  # Set volume on startup.

    self._snarks_wrapper.remove_snarks_listener(self)

    #def hmm():
    #  self.vlc_player.video_set_marquee_string(vlc.VideoMarqueeOption.Text, "hello")
    #wx.CallLater(10000, hmm)

    #def hmm():
    #  wx.GetApp().invoke_later(wx.GetApp().ACTION_DIE, {})
    #wx.CallLater(6000, hmm)

  def init_vlc(self):
    """Sets the window id where VLC will render video output.
    On platforms with GTK, this is only possible after the
    window has been created.
    """
    # Gotta mention marq in the instance for marquee methods to work.
    # Gotta show title for marquee to be visible.
    # Verbose -1 suppresses spam about "vlc_object_find_name" not being safe.
    self.vlc_obj = vlc.Instance("--video-title-show --video-title-timeout 1 --sub-source marq --verbose -1")
    self.vlc_player = self.vlc_obj.media_player_new()
    self.vlc_event_manager = None
    show_time_milliseconds = common.delta_seconds(self._config.show_time)*1000
    #self.vlc_player.video_set_marquee_int(vlc.VideoMarqueeOption.Enable, 1)
    self.vlc_player.video_set_marquee_int(vlc.VideoMarqueeOption.Position, vlc.Position.Bottom)
    self.vlc_player.video_set_marquee_int(vlc.VideoMarqueeOption.Refresh, 100)  # Milliseconds.
    self.vlc_player.video_set_marquee_int(vlc.VideoMarqueeOption.Timeout, show_time_milliseconds)  # Milliseconds. 0=Forever.
    #self.vlc_player.video_set_marquee_string(vlc.VideoMarqueeOption.Text, "aaaaaaaaaa")

    this_platform = platform.system()
    if (re.search("Linux", this_platform, re.IGNORECASE)):
      self.vlc_player.set_xwindow(self.video_panel.GetHandle())

    elif (re.search("Windows", this_platform, re.IGNORECASE)):
      self.vlc_player.set_hwnd(self.video_panel.GetHandle())

    elif (re.search("Darwin", this_platform, re.IGNORECASE)):
      # Reportedly this is broken.
      # In OSX, the vlc window can not be attached.
      # And there's some weirdness concerning wx on Carbon vs new Cocoa.
      self.vlc_player.set_nsobject(self.video_panel.GetHandle())
      # or self.vlc_player.set_agl(self.video_panel.GetHandle())

    else:
      logging.error("Could not associate VLC video overlay with the GUI window.")

    if (not self.vlc_event_manager):
      self.vlc_event_manager = self.vlc_player.event_manager()
      self.vlc_event_manager.event_attach(vlc.EventType.MediaPlayerMediaChanged, self._on_vlc_event)
      self.vlc_event_manager.event_attach(vlc.EventType.MediaPlayerSeekableChanged, self._on_vlc_event)
      self.vlc_event_manager.event_attach(vlc.EventType.MediaPlayerPausableChanged, self._on_vlc_event)
      self.vlc_event_manager.event_attach(vlc.EventType.MediaPlayerPlaying, self._on_vlc_event)
      self.vlc_event_manager.event_attach(vlc.EventType.MediaPlayerPaused, self._on_vlc_event)
      self.vlc_event_manager.event_attach(vlc.EventType.MediaPlayerStopped, self._on_vlc_event)
      self.vlc_event_manager.event_attach(vlc.EventType.MediaPlayerLengthChanged, self._on_vlc_event)
      self.vlc_event_manager.event_attach(vlc.EventType.MediaPlayerTimeChanged, self._on_vlc_event)

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

  def _trigger_statusbar_clear(self, e):
    self.statusbar.SetStatusText("", self.STATUS_HELP)
    if (e is not None): e.Skip(True)

  def _trigger_statusbar_clear_tip(self, e):
    """Clears the statusbar's help, only if its text was from hovering."""
    if (self._last_status_tip and self._last_status_tip == self.statusbar.GetStatusText()):
      self._trigger_statusbar_clear(None)
    self._last_status_tip = None
    if (e is not None): e.Skip(True)

  def _time_string(self, milliseconds):
    """Converts milliseconds into a 0:00:00 string, or --:-- if given None."""
    if (milliseconds is None): return "--:--"

    seconds = milliseconds // 1000
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if (hours > 0):
      return "%d:%02d:%02d" % (hours, minutes, seconds)
    else:
      return "%02d:%02d" % (minutes, seconds)

  def _on_open(self, e):
    """Open video file dialog."""
    # Weirdly, calling _on_stop() here while playing would hang.

    initial_dir = ""
    dlg = wx.FileDialog(self, "Choose a file", initial_dir, "", "*.*", wx.OPEN)
    if (dlg.ShowModal() == wx.ID_OK):
      vlc_media = self.vlc_obj.media_new(unicode(dlg.GetPath()))
      # Media options don't seem to work.
      #vlc_media.add_option("no-video-title-show")
      #vlc_media.add_option("sub-source marq{marquee=TweetSubs,position=8,timeout=10000}}")
      #vlc_media.add_option("sub-source marq{marquee=Hello,position=8}")
      #vlc_media.add_option("sub-source marq@test{marquee=zzzzzzzzzzzz,timeout=50000}")
      #vlc_media.add_option("marq-marquee=\"Hello\"")
      self.vlc_player.set_media(vlc_media)
      vlc_media.release()

      #self._on_play(None)

    dlg.Destroy()
    if (e is not None): e.Skip(False)  # Consume the event.

  def _on_snark_frame_destroyed(self, e):
    """Toggles the menuitem when the snarks window closes."""
    self.snark_frame = None
    self.snarks_menuitem.Enable(True)
    if (e is not None): e.Skip(True)

  def _on_show_snarks(self, e):
    """Shows the Snarks window and toggles the menuitem."""
    self.snark_frame = snarkgrid.SnarkFrame(self, wx.ID_ANY, "Snarks", self._snarks_wrapper)
    self.snark_frame.Show()
    self.snarks_menuitem.Enable(False)
    self.snark_frame.Bind(wx.EVT_WINDOW_DESTROY, self._on_snark_frame_destroyed)

  def _on_export(self, e):
    try:
      config = self._snarks_wrapper.clone_config()
      snarks = self._snarks_wrapper.clone_snarks()

      snarkutils.gui_postprocess_snarks(config, snarks)
      if (len(snarks) == 0):
        common.CompileSubsException("After postprocessing, no messages were left.")

      logging.info("Calling %s exporter..." % config.exporter_name)
      self.statusbar.SetStatusText("Calling %s exporter..." % config.exporter_name, self.STATUS_HELP)
      snarkutils.export_snarks(config, snarks)

      logging.info("Done.")
      self.statusbar.SetStatusText("Export succeeded.", self.STATUS_HELP)

    except (common.CompileSubsException) as err:
      # Exporter failed in an uninteresting way.
      logging.error(str(err))
      self.statusbar.SetStatusText("Error: %s" % str(err), self.STATUS_HELP)

    except (Exception) as err:
      logging.exception(err)
      self.statusbar.SetStatusText("Error: The exporter failed in an unexpected way.", self.STATUS_HELP)

    if (e is not None): e.Skip(False)  # Consume the event.

  def _on_close(self, e):
    if (self.snark_frame is not None): self.snark_frame.Close()

    if (self.vlc_event_manager is not None):
      self.vlc_event_manager.event_detach(vlc.EventType.MediaPlayerMediaChanged)
      self.vlc_event_manager.event_detach(vlc.EventType.MediaPlayerSeekableChanged)
      self.vlc_event_manager.event_detach(vlc.EventType.MediaPlayerPausableChanged)
      self.vlc_event_manager.event_detach(vlc.EventType.MediaPlayerPlaying)
      self.vlc_event_manager.event_detach(vlc.EventType.MediaPlayerPaused)
      self.vlc_event_manager.event_detach(vlc.EventType.MediaPlayerStopped)
      self.vlc_event_manager.event_detach(vlc.EventType.MediaPlayerLengthChanged)
      self.vlc_event_manager.event_detach(vlc.EventType.MediaPlayerTimeChanged)
      self.vlc_event_manager = None
    # Stopping vlc here causes hangs.
    # Luckily, vlc doesn't mind Destroy() while playing.

    self._snarks_wrapper.remove_snarks_listener(self)

    self.Destroy()
    if (e is not None): e.Skip(False)  # Consume the event.

  def _on_destroy(self, e):
    if (e is not None): e.Skip(True)

  def _on_play(self, e):
    if (self.vlc_player.play() != -1):
      self.pulse_timer.Start(milliseconds=250)
    else:
      self.statusbar.SetStatusText("Error: Unable to play.", self.STATUS_HELP)

    if (e is not None): e.Skip(False)  # Consume the event.

  def _on_pause(self, e):
    self.vlc_player.pause()
    if (e is not None): e.Skip(False)  # Consume the event.

  def _on_stop(self, e):
    self.vlc_player.stop()
    if (e is not None): e.Skip(False)  # Consume the event.

  def _on_seek_minus_ten(self, e):
    vlc_milliseconds = self.vlc_player.get_time()
    if (vlc_milliseconds == -1):
      self.statusbar.SetStatusText("Error: VLC reported a bad time. Aborting seek.", self.STATUS_HELP)
    else:
      self.vlc_player.set_time(vlc_milliseconds - 10*1000)

    if (e is not None): e.Skip(False)  # Consume the event.

  def _on_seek_plus_ten(self, e):
    vlc_milliseconds = self.vlc_player.get_time()
    if (vlc_milliseconds == -1):
      self.statusbar.SetStatusText("Error: VLC reported a bad time. Aborting seek.", self.STATUS_HELP)
    else:
      self.vlc_player.set_time(vlc_milliseconds + 10*1000)

    if (e is not None): e.Skip(False)  # Consume the event.

  def _on_pulse(self, e):
    # VLC's max is 200; slider's is 100. So multiply by 2.
    if (self.new_volume is not None):
      self.vlc_player.audio_set_volume(self.new_volume * 2)
      self.new_volume = None

    if (e is not None): e.Skip(False)  # Consume the event.

  def _on_scrub_start(self, e):
    self.scrubbing = True
    if (e is not None): e.Skip(True)  # Don't consume the event.

  def _on_scrub_end(self, e):
    if (self.scrubbing):
      self.vlc_player.set_time(self.timeslider.GetValue())
      self.scrubbing = False

      if (self.vlc_player.is_playing() == 0):
        vlc_milliseconds = self.vlc_player.get_time()
        if (vlc_milliseconds >= 0):
          self.statusbar.SetStatusText(self._time_string(vlc_milliseconds), self.STATUS_CLOCK)

    if (e is not None): e.Skip(True)  # Don't consume the event.

  def _on_adj_volume(self, e):
    self.new_volume = self.volslider.GetValue()
    if (e is not None): e.Skip(True)  # Don't consume the event.

  def _on_vlc_event(self, e):
    """Responds to VLC notifications.
    This is called by a non-GUI thread, so everything
    gets wrapped in a CallAfter().
    """
    if (e.type == vlc.EventType.MediaPlayerMediaChanged):
      def f():
        if (self.vlc_player is not None):
          vlc_media = self.vlc_player.get_media()
          if (vlc_media is not None):
            vlc_media.parse()
            title = vlc_media.get_meta(vlc.Meta.Title)
            self.SetTitle("%s - CompileSubs" % title)
          else:
            self.SetTitle("CompileSubs %s" % global_config.VERSION)

          self.vlc_player.play()
      wx.CallAfter(f)

    elif (e.type == vlc.EventType.MediaPlayerLengthChanged):
      logging.debug("VLC length changed.")
      def f():
        if (self.vlc_player is not None):
          length = self.vlc_player.get_length()
          self.timeslider.SetRange(-1, length)
          self.timeslider.SetPageSize(length // 20)
      wx.CallAfter(f)

    elif (e.type == vlc.EventType.MediaPlayerSeekableChanged):
      def f():
        if (self.vlc_player is not None):
          self.timeslider.Enable(self.vlc_player.is_seekable())
      wx.CallAfter(f)

    elif (e.type == vlc.EventType.MediaPlayerPausableChanged):
      logging.debug("VLC pausable changed.")
      def f():
        if (self.vlc_player is not None):
          self.pause_btn.Enable(self.vlc_player.can_pause())
      wx.CallAfter(f)

    elif (e.type == vlc.EventType.MediaPlayerPlaying):
      logging.debug("VLC playing.")
      def f():
        self.ctrl_panel.Freeze()
        self.play_btn.Show(False)
        self.pause_btn.Show(True)
        self.ctrl_panel.Thaw()
        self.ctrl_panel.Layout()
      wx.CallAfter(f)

    elif (e.type == vlc.EventType.MediaPlayerPaused):
      logging.debug("VLC paused.")
      def f():
        self.ctrl_panel.Freeze()
        self.pause_btn.Show(False)
        self.play_btn.Show(True)
        self.ctrl_panel.Thaw()
        self.ctrl_panel.Layout()
      wx.CallAfter(f)

    elif (e.type == vlc.EventType.MediaPlayerStopped):
      logging.debug("VLC stopped.")
      def f():
        self.pulse_timer.Stop()

        self.ctrl_panel.Freeze()
        self.timeslider.SetValue(0)
        self.play_btn.Show(True)
        self.pause_btn.Show(False)
        self.pause_btn.Enable(False)
        self.ctrl_panel.Thaw()
        self.ctrl_panel.Layout()
        self._last_video_time = None

        #clock_string = "%s/%s" % (self._time_string(None), self._time_string(None))
        #self.statusbar.SetStatusText(clock_string, self.STATUS_CLOCK)
        self.statusbar.SetStatusText(self._time_string(None), self.STATUS_CLOCK)
        self.statusbar.SetStatusText(self._time_string(None), self.STATUS_LENGTH)
      wx.CallAfter(f)

    elif (e.type == vlc.EventType.MediaPlayerTimeChanged):
      #logging.debug("VLC time changed.")
      def f():
        if (self.vlc_player is not None):
          vlc_milliseconds = self.vlc_player.get_time()
          if (vlc_milliseconds < 0): return

          if (not self.scrubbing): self.timeslider.SetValue(vlc_milliseconds)
          if (self.snark_frame is not None):
            vlc_seconds = vlc_milliseconds // 1000
            if (self._last_video_time is None or vlc_seconds != self._last_video_time):
              self._last_video_time = vlc_seconds
              self.snark_frame.set_video_time(vlc_milliseconds)

          #clock_string = "%s/%s" % (self._time_string(vlc_milliseconds), self._time_string(self.vlc_player.get_length()))
          #self.statusbar.SetStatusText(clock_string, self.STATUS_CLOCK)
          self.statusbar.SetStatusText(self._time_string(vlc_milliseconds), self.STATUS_CLOCK)
          self.statusbar.SetStatusText(self._time_string(self.vlc_player.get_length()), self.STATUS_LENGTH)
      wx.CallAfter(f)

    # VLC events have no Skip() to worry about.

  def on_snarks_changed(self, e):
    """Responds to config/snarks list changes.

    See common.SnarksWrapper.add_snarks_listener().

    :param e: A SnarksEvent.
    """
    if (common.SnarksEvent.FLAG_CONFIG_SHOW_TIME not in e.get_flags()):
      return

    self._config = e.get_source().clone_config()
    show_time_milliseconds = common.delta_seconds(self._config.show_time)*1000
    self.vlc_player.video_set_marquee_int(vlc.VideoMarqueeOption.Timeout, show_time_miliseconds)  # Milliseconds. 0=Forever.

  def show_vlc_message(self, text):
    """Displays a string over vlc's video."""
    self.vlc_player.video_set_marquee_string(vlc.VideoMarqueeOption.Text, text)

  def set_vlc_time(self, milliseconds):
    """Seeks to a new time in the video."""
    self.vlc_player.set_time(milliseconds)

  def get_vlc_time(self):
    """Returns the current time in the video (milliseconds)."""
    return self.vlc_player.get_time()