CompileSubs
===========
This takes a text transcript of datestamped commentary, made by
multiple people watching copies of the same video independently, and
transforms it into another format. The time of each person's
comments can be shifted to correct for buffering, pausing, starting
early/late, etc.

<img src="https://raw.github.com/Vhati/CompileSubs/master/img/screenshot01.png" width="145px" height="auto" />

It can read from the following sources:
* Html MockTM event transcripts from the [LousyCanuck blog](http://freethoughtblogs.com/lousycanuck/?s=Mock+The+Movie+transcript).
* Logs from [TweetSubs](https://github.com/Vhati/TweetSubs), an app that collects comments live from Twitter.
* A Twitter search for tweets from an account and @replies to it.
* Tabbed text.

And it can write:
* SubRip subtitles.
* Tabbed text.
* Html transcripts.
* Html transcripts, posted directly to a Wordpress blog.

More parser and exporter modules can be added fairly easily.


Requirements
------------
The commandline interface only needs Python, and should run well
on any os. The GUI is more demanding... it will run on Windows
and Linux; no idea about OSX.

* Python 2.6 or higher, but not 3.x.
    * http://www.python.org/getit/
* VLC 2.x.x
    * http://www.videolan.org/vlc/
* wxPython 2.8
    * http://www.wxpython.org/download.php

&nbsp;

**Note:** You can't mix 32bit and 64bit.

VLC is typically 32bit, so you'll need 32bit Python to match. Though there's an experimental 64bit VLC...
