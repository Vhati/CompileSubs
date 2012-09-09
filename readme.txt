CompileSubs v2.50

Author:
  David Millis (tvtronix@yahoo.com)


About

  This takes a text transcript of datestamped commentary, made by
multiple people watching copies of the same video independently, and
transforms it into another format. Each person's comments can be
shifted to correct for buffering, pausing, starting early/late, etc.

  It can read from the following sources:
    Html MockTM event transcripts from the LousyCanuck blog.
    Logs from TweetSubs, an app that collects comments live from Twitter.
    A Twitter search for tweets from an account and @replies to it.
    Tabbed text.

  And it can write:
    SubRip subtitles.
    Tabbed text.
    Html transcripts.
    Html transcripts, posted directly to a Wordpress blog.

  More parser and exporter modules can be added fairly easily.



Usage

Edit config.py.

Double-click compilesubs.py
(To hide the debugging console, rename it to .pyw)
(Linux and OSX should set permissions to make it executable)
OR
From a terminal, run: python compilesubs.py



Changes

2.50 - Broke up the monolithic code into parser/exporter modules.
       Updated transcript_lousycanuck parser's snark_ptn regex.
       Tweaked the tweetsubs_log parser to include tweets that had expired.
       Added pickled_snarks parser/exporter.
       Added twitter_search parser.
       Added tabbed_text parser and exporter.
       Added transcript_html exporter.
       Added transcript_wordpress exporter.
       Added an end_time setting to truncate at an in-movie time.
       Added prompting at runtime for sensitive config settings.
       Added this readme.
       Added logging.
       Renamed project from "MockTM Subtitles" to "CompileSubs".
2.40 - Added a parser for TweetSubs logs (the live script).
       Added support for multiline snarks in write_srt(), if sources provide them.
       Added a color demo subtitle at 0:00:01 to check the random palette mixture.
2.30 - Fixed a bug that broke filtering out negative times.
       Reworked delta_str() to use formatted math instead of scraping.
       Adjusted reply_ptn to leave a space when @MockTM appears mid-sentence.
       Updated the tail_ptn regex that stops parsing blog articles.
       Added an apostrophe variant to asciify().
2.20 - Moved blog-fetch code to a func, room for alternate sources (fetch_snarks_from_somewhere(...)).
       Moved srt writing into a func.
       Added color.
       Wrote docstrings for funcs.
2.10 - The 1st unskipped tweet's "date" decides the 0:00 movie "time" for the rest,
       even if negative "time" delays would drop that msg from the subtitles.
2.00 - Added per-user fudging.
       Added negative time checking.



Requirements

Python 2.6 or higher, but not 3.x.
  http://www.python.org/getit/
