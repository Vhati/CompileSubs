from datetime import datetime, timedelta
from lib.common import prompt

# These following are all the user-editable config vars.

# Sensitive values can be prompted at runtime.
#   xyz = prompt("user: ")
#   xyz = prompt("pass: ", hidden=True)
# Or have the filesystem revoke other users' read access to this file.



# Parser module name.
#   See files in the "./lib/parsers/" directory for details.
#   Choices: pickled_snarks, tabbed_text, transcript_lousycanuck,
#            tweetsubs_log, twitter_search
#
parser_name = "tweetsubs_log"

# Exporter module name.
#   See files in the "./lib/exporters/" directory for details.
#   Choices: pickled_snarks, subrip, tabbed_text, transcript_html,
#            transcript_wordpress
#
exporter_name = "subrip"


# Source to parse.
#   Examples:
#     http://freethoughtblogs.com/lousycanuck/transcript-post-name/
#     file:///saved-post.txt (relative to filesystem root)
#     file:saved-post.txt (relative to current dir)
#
src_path = "file:./log_2889.txt"

# Destination to write.
dest_path = "MockTM - In the Year 2889.srt"


# Optional substring to expect of the first tweeted message.
#   Use this to skip early msgs, or set to None.
first_msg = "And go!"


# Use this to delay all msgs (+/-).
fudge_time = timedelta(minutes=0, seconds=0)

# Users egregiously out of sync can be additionally offset (+/-).
# Later parts of the movie may need different fudging as users pause/buffer/etc.
#   Each user gets a list of paired deltas: when to fudge, and how much.
#   [(in-movie time, delay thereafter), (in-movie time, delay), ...]
#
fudge_users = {}
fudge_users["@brx0"] = [(timedelta(minutes=0, seconds=0), timedelta(minutes=0, seconds=0))]
# ...


# Optional in-movie time to truncate msgs (after fudging).
#   Use this to skip late msgs, or set to None.
#   end_time = timedelta(hours=2, minutes=0, seconds=0)
#
end_time = timedelta(hours=1, minutes=19, seconds=45)


# Colored subtitles
#   Choices: no,random,default
#     no: there will be no color info.
#     random: assign colors to users randomly.
#     default: let the parser decide.
#   At low resolutions, colored text can be ugly in VLC.
color_enabled = "random"

# Duration each msg appears on-screen.
show_time = timedelta(seconds=6)

# Parser-specific options.
parser_options = {}
parser_options["lousycanuck.reply_name"] = "MockTM"
parser_options["twitter_search.reply_name"] = "MockTM"
parser_options["twitter_search.since_date"] = datetime(2012, 8, 30)
parser_options["twitter_search.until_date"] = datetime(2012, 9, 1)
parser_options["twitter_search.passes"] = 7

# Exporter-specific options.
exporter_options = {}
exporter_options["subrip.include_names"] = True
exporter_options["transcript_html.faux_twitter_links"] = True
exporter_options["transcript_wordpress.xmlrpc_url"] = "http://.../xmlrpc.php"
exporter_options["transcript_wordpress.blog_user"] = ""
exporter_options["transcript_wordpress.blog_pass"] = ""
exporter_options["transcript_wordpress.post_title"] = ""
