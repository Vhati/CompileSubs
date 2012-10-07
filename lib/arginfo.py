DATETIME = "DATETIME"
TIMEDELTA = "TIMEDELTA"
BOOLEAN = "BOOLEAN"
INTEGER = "INTEGER"
STRING = "STRING"
HIDDEN_STRING = "HIDDEN_STRING"
FILE = "FILE"
URL = "URL"
FILE_OR_URL = "FILE_OR_URL"

class Arg(object):
  """Meta information about an expected argument."""
  def __init__(self, name="", type=None, required=False, default=None, choices=None, multiple=False, description="", current_value=None):
    object.__init__(self)
    self.name = name
    self.type = type
    self.required = required
    self.default = default
    self.choices = choices
    self.multiple = multiple
    self.description = description
    self.current_value = current_value
