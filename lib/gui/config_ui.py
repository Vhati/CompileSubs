from datetime import datetime, timedelta
import logging
import re
import wx
from wx.lib import filebrowsebutton

from lib import arginfo
from lib import common


EVT_RELAYOUT_TYPE = wx.NewEventType()
EVT_RELAYOUT = wx.PyEventBinder(EVT_RELAYOUT_TYPE, 1)


class ConfigSection(object):
  def __init__(self, name, subsections=None):
    """Constructor.

    :param name: The name of the subsection.
    :param subsections: A list of ConfigSubSection objects.
    """
    object.__init__(self)
    self.name = name
    self.subsections = subsections
    if (self.subsections is None): self.subsections = []

  def append_subsection(self, subsection):
    self.subsections.append(subsection)


class ConfigSubSection(object):
  def __init__(self, name, description="", args=None, apply_func=None):
    """Constructor.

    :param name: The name of the subsection.
    :param description: A description of the subsection.
    :param args: A list of arginfo.Arg objects.
    :param apply_func: A callback that takes 1 arg: a dict of arg values indexed by name.
    """
    object.__init__(self)
    self.name = name
    self.description = description
    self.args = args
    if (self.args is None): self.args = []
    self.apply_func = apply_func


class ConfigFrame(wx.Frame):
  def __init__(self, *args, **kwargs):
    self.custom_args = {"sections":[],"continue_func":None}
    for k in self.custom_args.keys():
      if (k in kwargs):
        self.custom_args[k] = kwargs[k]
        del kwargs[k]

    wx.Frame.__init__(self, *args, **kwargs)
    self.STATUS_FIELDS = ["STATUS_HELP", "STATUS_CORNER"]
    for (i, x) in enumerate(self.STATUS_FIELDS): setattr(self, x, i)

    self._sections = self.custom_args["sections"]
    self.continue_func = self.custom_args["continue_func"]
    self.args_panels = {}

    self.statusbar = self.CreateStatusBar()
    self.statusbar.SetFieldsCount(len(self.STATUS_FIELDS))
    self.statusbar.SetStatusWidths([-1, 17])
    self.statusbar.SetStatusStyles([wx.SB_NORMAL]*1+[wx.SB_FLAT])
    self.SetStatusBar(self.statusbar)

    self._pane = wx.Panel(self, wx.ID_ANY)
    pane_sizer = wx.BoxSizer(wx.VERTICAL)
    self._pane.SetSizer(pane_sizer)

    sections_nb = wx.Notebook(self._pane, wx.ID_ANY)

    for section in self._sections:
      self.args_panels[section.name] = {}
      section_panel = wx.Panel(sections_nb, wx.ID_ANY)
      section_sizer = wx.BoxSizer(wx.VERTICAL)

      section_header_panel = wx.Panel(section_panel, wx.ID_ANY, style=wx.RAISED_BORDER)
      section_header_sizer = wx.BoxSizer(wx.HORIZONTAL)
      section_header_sizer.Add((-1,45))
      subsection_field = wx.Choice(section_header_panel, wx.ID_ANY, choices=[x.name for x in section.subsections])
      section_header_sizer.Add(subsection_field, flag=wx.ALIGN_CENTER_VERTICAL|wx.LEFT, border=5)
      section_label = StaticWrapText(section_header_panel, wx.ID_ANY, label="")
      section_header_sizer.Add(section_label, 1, flag=wx.ALIGN_CENTER_VERTICAL|wx.LEFT, border=15)
      section_header_panel.SetSizer(section_header_sizer)
      section_sizer.Add(section_header_panel, flag=wx.EXPAND|wx.ALL, border=10)

      def subsection_change_callback(e, subsection_field=subsection_field, section=section, section_panel=section_panel, section_label=section_label):
        # Bake localized vars as func arg defaults because closure would use values from the final loop.
        n = subsection_field.GetSelection()
        selected_name = subsection_field.GetString(n)
        section_panel.Freeze()
        for subsection in section.subsections:
          self.args_panels[section.name][subsection.name].Show((subsection.name == selected_name))
          if (subsection.name == selected_name): section_label.SetLabel(subsection.description)
        section_panel.Layout()
        section_panel.Thaw()
        self.statusbar.SetStatusText("", self.STATUS_HELP)
      subsection_field.Bind(wx.EVT_CHOICE, subsection_change_callback)

      for subsection in section.subsections:
        apply_callback = None
        if (subsection.apply_func is not None):
          def apply_callback(values_dict, subsection=subsection):
            if (values_dict is not None):
              subsection.apply_func(values_dict)
              self.statusbar.SetStatusText("New values for %s were set." % subsection.name, self.STATUS_HELP)
            else:
              self.statusbar.SetStatusText("Error: Some %s values were invalid." % subsection.name, self.STATUS_HELP)
        args_panel = ArgsPanel(section_panel, wx.ID_ANY, args=subsection.args, apply_func=apply_callback)
        args_panel.Show(False)
        self.args_panels[section.name][subsection.name] = args_panel
        section_sizer.Add(args_panel, 1, flag=wx.EXPAND)
      if (len(section.subsections) > 0):
        subsection_field.SetSelection(0)
        subsection_change_callback(None)

      section_panel.SetSizer(section_sizer)
      sections_nb.AddPage(section_panel, section.name)

    pane_sizer.Add(sections_nb, 1, flag=wx.EXPAND)
    pane_sizer.Add((-1,5))

    if (self.continue_func is not None):
      def continue_callback(e):
        self.Close()
        self.continue_func()
      continue_btn = wx.Button(self._pane, wx.ID_ANY, label="Continue", style=wx.BU_EXACTFIT)
      pane_sizer.Add(continue_btn, flag=wx.ALIGN_CENTER_HORIZONTAL|wx.ALL, border=5)
      continue_btn.Bind(wx.EVT_BUTTON, continue_callback)

    sizer = wx.BoxSizer(wx.VERTICAL)
    sizer.Add(self._pane, 1, flag=wx.EXPAND)
    self.SetSizer(sizer)

    self.Fit()
    self.SetSize((self.GetSize()[0]+30, 400))

    for section in self._sections:
      for subsection in section.subsections:
        self.args_panels[section.name][subsection.name].init_scrollbars()

    self.Bind(EVT_RELAYOUT, self._on_relayout)

  def _on_relayout(self, e):
    self._args_scroll.Refresh()
    self._args_scroll.Update()
    if (e is not None): e.Skip(True)


class ArgsPanel(wx.Panel):
  """A scrollable list of ArgPanels."""
  def __init__(self, *args, **kwargs):
    self.custom_args = {"args":[],"apply_func":None}
    for k in self.custom_args.keys():
      if (k in kwargs):
        self.custom_args[k] = kwargs[k]
        del kwargs[k]

    wx.Panel.__init__(self, *args, **kwargs)

    self._arg_panels = []
    self._apply_func = self.custom_args["apply_func"]

    sizer = wx.BoxSizer(wx.VERTICAL)

    self._args_scroll = wx.ScrolledWindow(self, wx.ID_ANY, style=wx.VSCROLL|wx.SUNKEN_BORDER)
    args_sizer = wx.BoxSizer(wx.VERTICAL)
    value_width = 1
    for arg in self.custom_args["args"]:
      arg_panel = ArgPanel(self._args_scroll, wx.ID_ANY, arg=arg, style=wx.RAISED_BORDER)
      value_width = max(value_width, arg_panel.get_preferred_value_column_width())
      self._arg_panels.append(arg_panel)
      args_sizer.Add(arg_panel, flag=wx.EXPAND)
    for arg_panel in self._arg_panels:
      arg_panel.set_value_column_width(value_width)
    if (len(self._arg_panels) == 0):
      dummy_panel = wx.Panel(self._args_scroll, wx.ID_ANY, style=wx.RAISED_BORDER)
      dummy_sizer = wx.BoxSizer(wx.VERTICAL)
      dummy_label = wx.StaticText(dummy_panel, wx.ID_ANY, label="No args.")
      dummy_sizer.Add(dummy_label, flag=wx.ALIGN_CENTER_HORIZONTAL|wx.ALL, border=15)
      dummy_panel.SetSizer(dummy_sizer)
      args_sizer.Add(dummy_panel, flag=wx.EXPAND)
    else:
      ctrl_panel = wx.Panel(self._args_scroll, wx.ID_ANY, style=wx.RAISED_BORDER)
      ctrl_sizer = wx.BoxSizer(wx.VERTICAL)
      apply_btn = wx.Button(ctrl_panel, wx.ID_ANY, label="Apply Changes", style=wx.BU_EXACTFIT)
      ctrl_sizer.Add(apply_btn, flag=wx.ALIGN_RIGHT|wx.ALL, border=15)
      ctrl_panel.SetSizer(ctrl_sizer)
      args_sizer.Add(ctrl_panel, flag=wx.EXPAND)

      def apply_callback(e):
        values = None
        if (self.validate() is True): values = self.get_values_as_dict()
        if (self._apply_func is not None):
          self._apply_func(values)
      apply_btn.Bind(wx.EVT_BUTTON, apply_callback)
    self._args_scroll.SetSizer(args_sizer)
    sizer.Add(self._args_scroll, 1, flag=wx.EXPAND)

    self.SetSizer(sizer)

    self.Bind(EVT_RELAYOUT, self._on_relayout)

  def init_scrollbars(self):
    """Enables the scrollbars late, which otherwise interfere with frame fitting."""
    self._args_scroll.SetScrollRate(10,10)

  def validate(self, verbose=False):
    """Calls validate() on all nested ArgPanels.

    :param verbose: True to log the errors, False to suppress.
    :returns: True if all are valid, False otherwise.
    """
    result = True
    for arg_panel in self._arg_panels:
      if (arg_panel.validate(verbose) is False): result = False
    return result

  def get_value_by_name(self, name):
    """Calls get_value() on the nested ArgPanel of a specific Arg.

    :param name: The Arg's name.
    :returns: The result of that call, or (None, None).
    """
    for arg_panel in self._arg_panels:
      if (arg_panel.get_arg() == name):
        return arg_panel.get_value()
    return None, None

  def get_values_as_dict(self):
    """Returns a dict of all nested ArgPanels' values, indexed by name.
    Invalid ArgPanels are omitted.
    """
    result = {}
    for arg_panel in self._arg_panels:
      value, errors = arg_panel.get_value()
      if (not errors): result[arg_panel.get_arg().name] = value
    return result

  def _on_relayout(self, e):
    self._args_scroll.Refresh()
    self._args_scroll.Update()
    if (e is not None): e.Skip(True)


class ArgPanel(wx.Panel):
  """A panel for displaying/setting an argnfo.Arg object."""
  def __init__(self, *args, **kwargs):
    self.custom_args = {"arg":None}
    for k in self.custom_args.keys():
      if (k in kwargs):
        self.custom_args[k] = kwargs[k]
        del kwargs[k]
    if (self.custom_args["arg"] is None):
      self.custom_args["arg"] = arginfo.Arg()

    wx.Panel.__init__(self, *args, **kwargs)

    self._arg = self.custom_args["arg"]
    self._value_fields = []
    self._browsefield_width = 175
    self._textfield_width = 125

    info_value_sizer = wx.BoxSizer(wx.HORIZONTAL)

    toggle_sizer = wx.BoxSizer(wx.VERTICAL)
    self._toggle_check = wx.CheckBox(self, wx.ID_ANY, label="")
    self._toggle_check.SetValue(True)
    if (self._arg.required): self._toggle_check.Enable(False)
    self._toggle_check.Bind(wx.EVT_CHECKBOX, self._on_toggle)
    toggle_sizer.Add(self._toggle_check)
    toggle_sizer.Add((self._toggle_check.GetEffectiveMinSize().width,-1), 1)
    self._invalid_label = wx.StaticText(self, wx.ID_ANY, label="!")
    self._invalid_label.SetFont(wx.Font(11, wx.DEFAULT, wx.NORMAL, wx.BOLD))
    self._invalid_label.SetForegroundColour((200,20,20))
    self._invalid_label.Show(False)
    toggle_sizer.Add(self._invalid_label, flag=wx.ALIGN_CENTER_HORIZONTAL|wx.ALIGN_CENTER_VERTICAL)
    toggle_sizer.Add((-1,-1), 1)
    info_value_sizer.Add(toggle_sizer, flag=wx.EXPAND|wx.LEFT, border=5)

    label_sizer = wx.BoxSizer(wx.VERTICAL)
    name_label = wx.StaticText(self, wx.ID_ANY, label=self._arg.name)
    label_sizer.Add(name_label, flag=wx.LEFT|wx.BOTTOM, border=4)
    toggle_sizer.Add((-1,5))
    desc_label = wx.StaticText(self, wx.ID_ANY, label=self._arg.description)
    label_sizer.Add(desc_label, flag=wx.LEFT|wx.BOTTOM, border=4)
    toggle_sizer.Add((-1,-1), 1)
    info_value_sizer.Add(label_sizer, 1, flag=wx.EXPAND)

    sep_line = wx.StaticLine(self, wx.ID_ANY, style=wx.LI_VERTICAL)
    info_value_sizer.Add(sep_line, flag=wx.EXPAND|wx.ALIGN_CENTER_HORIZONTAL|wx.LEFT|wx.RIGHT, border=15)

    self._value_panel = wx.Panel(self, wx.ID_ANY)
    value_sizer = wx.BoxSizer(wx.VERTICAL)
    value_sizer.Add((-1,-1), 1)

    value_field = (-1,-1)
    self._fields_sizer = wx.BoxSizer(wx.VERTICAL)
    # This will be populated later.
    value_sizer.Add(self._fields_sizer, flag=wx.ALIGN_RIGHT)

    if (self._arg.multiple is True):
      value_sizer.Add((-1,10))
      multiple_sizer = wx.BoxSizer(wx.HORIZONTAL)
      self._remove_field_btn = wx.Button(self._value_panel, wx.ID_ANY, label="Rem", style=wx.BU_EXACTFIT)
      self._shrink_button(self._remove_field_btn)
      self._remove_field_btn.Bind(wx.EVT_BUTTON, self._on_remove_field)
      multiple_sizer.Add(self._remove_field_btn)
      multiple_sizer.Add((15,-1))
      self._add_field_btn = wx.Button(self._value_panel, wx.ID_ANY, label="Add", style=wx.BU_EXACTFIT)
      self._shrink_button(self._add_field_btn)
      self._add_field_btn.Bind(wx.EVT_BUTTON, self._on_add_field)
      multiple_sizer.Add(self._add_field_btn)
      value_sizer.Add(multiple_sizer, flag=wx.ALIGN_RIGHT)

    self._value_spacer = wx.SizerItem()
    self._value_spacer.SetProportion(1)
    self._value_spacer.AssignSpacer((-1,-1))
    value_sizer.AddItem(self._value_spacer)

    self._value_panel.SetSizer(value_sizer)
    info_value_sizer.Add(self._value_panel, flag=wx.EXPAND|wx.RIGHT, border=5)

    sizer = wx.BoxSizer(wx.VERTICAL)
    sizer.Add(info_value_sizer, 1, flag=wx.EXPAND|wx.TOP|wx.BOTTOM, border=4)
    self.SetSizer(sizer)

    self._on_add_field(None)  # Add the first field.
    if (self._arg.current_value is not None):
      if (self._arg.multiple is True):
        for i in range(len(self._arg.current_value)-1): self._on_add_field(None)
        for (f,v) in zip(self._value_fields, self._arg.current_value):
          self._set_field_value(f, v)
      else:
        self._set_field_value(self._value_fields[0], self._arg.current_value)

    self._preferred_value_column_width = self._value_panel.GetEffectiveMinSize().width

    enable = True
    if (self._arg.required is True):
      enable = True  # Required.
      self._toggle_check.Show(False)
    elif (self._arg.current_value is None):
      enable = False  # Optional and current value is None.
    elif (self._arg.multiple is True and len(self._arg.current_value) == 0):
      enable = False  # Optional and current value is an empty list.

    self._toggle_check.SetValue(enable)
    self._on_toggle(None)

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

  def get_arg(self):
    """Returns the arg this panel was constructed from."""
    return self._arg

  def get_preferred_value_column_width(self):
    """Returns the MinEffectiveSize width as it was prior to setting the width spacer."""
    return self._preferred_value_column_width

  def set_value_column_width(self, n):
    """Sets a spacer's width in the value column."""
    self._value_spacer.AssignSpacer((n,-1))
    self.Layout()
    self._relayout_parent()

  def _set_invalid_label_visible(self, b):
    """Toggles visibility of the invalidity label."""
    if (self._invalid_label.IsShownOnScreen() is not b):
      self._invalid_label.Show(b)
      self.Layout()

  def _on_toggle(self, e):
    is_enabled = self._toggle_check.IsChecked()
    self._value_panel.Enable(is_enabled)
    if (is_enabled is False): self._set_invalid_label_visible(False)

    if (e is not None): e.Skip(False)  # Consume the event.

  def _on_remove_field(self, e):
    if (len(self._value_fields) <= 1): return
    self._value_fields.pop().Destroy()

    self._relayout_parent()

    if (e is not None): e.Skip(False)  # Consume the event.

  def _on_add_field(self, e):
    if (self._arg.choices is not None):
      value_field = wx.Choice(self._value_panel, wx.ID_ANY)
      for x in self._arg.choices: value_field.Append(str(x), x)
      if (self._arg.default is not None):
        value_field.SetSelection(self._arg.choices.index(self._arg.default))
    elif (self._arg.type == arginfo.TIMEDELTA):
      default_str = common.delta_str(timedelta(0))
      if (self._arg.default is not None): default_str = common.delta_str(self._arg.default)
      value_field = wx.TextCtrl(self._value_panel, wx.ID_ANY, size=(self._textfield_width,-1), value=default_str)
    elif (self._arg.type == arginfo.DATETIME):
      default_str = "0000-00-00"
      if (self._arg.default is not None): default_str = self._arg.default.strftime("%Y-%m-%d")
      value_field = wx.TextCtrl(self._value_panel, wx.ID_ANY, size=(self._textfield_width,-1), value=default_str)
    elif (self._arg.type == arginfo.FILE):
      default_str = ""
      if (self._arg.default is not None): default_str = self._arg.default
      value_field = wx.lib.filebrowsebutton.FileBrowseButton(self._value_panel, wx.ID_ANY, labelText="", buttonText="File...")
      value_field.textControl.SetInitialSize((self._browsefield_width,-1))
      value_field.browseButton.SetWindowStyleFlag(value_field.browseButton.GetWindowStyleFlag()|wx.BU_EXACTFIT)
      value_field.SetValue(default_str, 0)
    elif (self._arg.type == arginfo.FILE_OR_URL):
      def file_callback(e):
        source = e.GetEventObject()
        if (isinstance(source, wx.TextCtrl)):
          ipoint = source.GetInsertionPoint()
          old_value = source.GetValue()
          new_value = re.sub("\\\\", "/", old_value)
          has_schema = False

          if (re.match("^file:", new_value) is not None): has_schema = True
          elif (re.match("(?i)^[a-z]{2,}:/($|/)", new_value) is not None): has_schema = True

          if (has_schema is False):
            m = re.search("(?i)^[a-z]:/", new_value)
            if (m is not None):
              new_value = new_value[0:m.start(0)] + m.expand("file:///\g<0>") + new_value[m.end(0):]
              ipoint += 8
              has_schema = True
          if (has_schema is False):
            m = re.search("^[^/]*/", new_value)
            if (m is not None):
              new_value = "file:"+ new_value
              ipoint += 5
              has_schema = True
          if (new_value != old_value):
            source.SetValue(new_value)
            source.SetInsertionPoint(ipoint)
      default_str = ""
      if (self._arg.default is not None): default_str = self._arg.default
      value_field = wx.lib.filebrowsebutton.FileBrowseButton(self._value_panel, wx.ID_ANY, labelText="", buttonText="File...", changeCallback=file_callback)
      value_field.textControl.SetInitialSize((self._browsefield_width,-1))
      value_field.browseButton.SetWindowStyleFlag(value_field.browseButton.GetWindowStyleFlag()|wx.BU_EXACTFIT)
      value_field.SetValue(default_str, 0)
    elif (self._arg.type == arginfo.HIDDEN_STRING):
      default_str = ""
      if (self._arg.default is not None): default_str = self._arg.default
      value_field = wx.TextCtrl(self._value_panel, wx.ID_ANY, style=wx.TE_PASSWORD, size=(self._textfield_width,-1), value=default_str)
    elif (self._arg.type == arginfo.STRING):
      default_str = ""
      if (self._arg.default is not None): default_str = self._arg.default
      value_field = wx.TextCtrl(self._value_panel, wx.ID_ANY, size=(self._textfield_width,-1), value=default_str)
    else:  # boolean, integer, url
      default_str = ""
      if (self._arg.default is not None):
        default_str = self._arg.default
        if (isinstance(default_str, basestring) is False): default_str = repr(default_str)
      value_field = wx.TextCtrl(self._value_panel, wx.ID_ANY, size=(self._textfield_width,-1), value=default_str)
    self._value_fields.append(value_field)
    self._fields_sizer.Add(value_field, flag=wx.ALIGN_RIGHT)

    self._relayout_parent()

    if (e is not None): e.Skip(False)  # Consume the event.

  def _set_field_value(self, field, value):
    if (self._arg.choices is not None):
      field.SetSelection(self._arg.choices.index(value))
    elif (self._arg.type == arginfo.TIMEDELTA):
      field.SetValue(common.delta_str(value))
    elif (self._arg.type == arginfo.DATETIME):
      field.SetValue(value.strftime("%Y-%m-%d"))
    elif (self._arg.type in [arginfo.STRING, arginfo.HIDDEN_STRING, arginfo.FILE, arginfo.URL]):
      field.SetValue(value)
    elif (self._arg.type == arginfo.FILE_OR_URL):
      field.SetValue(value, 0)
    elif (self._arg.type in [arginfo.INTEGER, arginfo.BOOLEAN]):
      field.SetValue(repr(value))

  def _fire_layout_event(self):
    event = wx.PyCommandEvent(EVT_RELAYOUT_TYPE, self.GetId())
    event.SetEventObject(self)
    self.GetEventHandler().ProcessEvent(event)

  def _relayout_parent(self):
    parent = self.GetParent()
    if (parent is not None):
      parent.Layout()
      parent.Refresh()  # Mark the parent as dirty.
      parent.Update()   # Repaint.
      #self._fire_layout_event()

  def validate(self, verbose=False):
    """Tests whether the arg is satisfied.
    An exclamation mark will appear if invalid.

    :param verbose: True to log the errors, False to suppress.
    :returns: True if valid, False otherwise.
    """
    value, errors = self.get_value()
    if (errors):
      if (verbose is True):
        for err_str in errors: logging.error(err_str)
      self._set_invalid_label_visible(True)
      return False
    else:
      return True

  def get_value(self):
    """Parses the field(s) into the Arg's native type.
    Disabled optional args have a value of None.

    :returns: The parsed result, and a list of error messages (which may be None).
    """
    if (self._toggle_check.IsChecked() is False):
      if (self._arg.multiple is True):
        return [], None
      else:
        return None, None

    results = []
    errors = []
    for field in self._value_fields:
      if (self._arg.choices is not None):
        choice = field.GetClientData(field.GetSelection())
        results.append(choice)
      else:
        value = field.GetValue()
        try:
          if (self._arg.type == arginfo.TIMEDELTA):
            results.append(common.delta_from_str(value))
          elif (self._arg.type == arginfo.DATETIME):
            if (value == "" or re.match("^0+-0+-0+$", value) is not None or re.match("^[0-9]{4}-[0-9]{2}-[0-9]{2}$", value) is None):
              raise ValueError("Date expected (####-##-##), not \"%s\"." % value)
            results.append(datetime.strptime(value, "%Y-%m-%d"))
          elif (self._arg.type == arginfo.BOOLEAN):
            if (value not in ["True","False"]):
              raise ValueError("Boolean expected (True/False), not \"%s\"." % value)
            results.append(True if (value == "True") else False)
          elif (self._arg.type == arginfo.INTEGER):
            if (re.match("^[0-9]+$", value) is None):
              raise ValueError("Integer expected, not \"%s\"." % value)
            results.append(int(value))
          elif (self._arg.type in [arginfo.URL, arginfo.FILE_OR_URL]):
            if (re.match("(?i)^[a-z]{2,}:", value) is None):
              raise ValueError("URI schema expected (abc:), not \"%s\"." % value)
            results.append(value)
          elif (self._arg.type in [arginfo.STRING, arginfo.HIDDEN_STRING, arginfo.FILE]):
            if (value == ""):
              raise ValueError("Empty strings are not allowed.")
            results.append(value)
          else:
            raise NotImplementedError("Unexpected arg type: %s" % self._arg.type)

        except (ValueError) as err:
          errors.append("While parsing arg %s: %s" % (self._arg.name, str(err)))
          results.append(None)

    if (len(errors) == 0): errors = None

    if (self._arg.multiple):
      return results, errors
    else:
      return results[0], errors


class StaticWrapText(wx.PyControl):
  """A StaticText that does word wrapping.
  Its vertical growth is a little weird because its next
  height is based on the previous width. So it would take
  two similar resize events to come out right.
  """
  def __init__(self, parent, id=wx.ID_ANY, label='', pos=wx.DefaultPosition,
               size=wx.DefaultSize, style=wx.NO_BORDER,validator=wx.DefaultValidator,
               name='StaticWrapText'):
    wx.PyControl.__init__(self, parent, id, pos, size, style, validator, name)
    self.st = wx.StaticText(self, wx.ID_ANY, label="", style=style)
    self._raw_text = label
    self._wrapped_height = 50
    self._rewrapping = False
    self._rewrap()
    self.Bind(wx.EVT_SIZE, self.OnSize)

  def SetLabel(self, label):
    self._raw_text = label
    self._rewrap()
  def GetLabel(self):
    return self._raw_text

  def SetFont(self, font):
    self.st.SetFont(font)
    self.rewrap()
  def GetFont(self):
    return self.st.GetFont()

  def OnSize(self, e):
    self.st.SetSize(self.GetSize())
    if (not self._rewrapping):
      self._rewrapping = True
      self._rewrap()
      self._rewrapping = False
    if (e is not None): e.Skip(True)

  def _rewrap(self):
    parent = self.GetParent()
    if (parent is not None): parent.Freeze()
    self.st.SetLabel(self._raw_text)
    self.st.Wrap(self.GetSize().width)
    self._wrapped_height = self.st.GetEffectiveMinSize().height
    if (parent is not None):
      parent.Layout()
      parent.Thaw()

  def DoGetBestSize(self):
    return wx.Size(100, self._wrapped_height)
