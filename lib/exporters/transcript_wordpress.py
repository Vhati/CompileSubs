from datetime import datetime, timedelta
import contextlib
import logging
import re
import StringIO
import sys
import xmlrpclib

from lib import common


# Namespace for options.
ns = "transcript_wordpress."

# Whether dest_file arg is used.
needs_file = False


def write_snarks(dest_file, snarks, show_time, options={}):
  """Writes snarks to a new Wordpress blog post.

  RPC support needs to be enabled on the server.
  See: http://codex.wordpress.org/XML-RPC_Support

  This plugin requires blog credentials. Unless this script
  is being run from a trusted environment, you should
  use filesystem permissions to prevent other users from
  reading the config file.

  :param dest_file: Not used.
  :param snarks: A list of processed snark dicts.
  :param show_time: Timedelta duration each msg appears on-screen.
  :param options: A dict of extra options specific to this exporter.
                  xmlrpc_url:
                      Full url to "http://.../xmlrpc.php".
                  blog_id (optional):
                      Usually ignored by Wordpress servers. Default is 0.
                  blog_user:
                      Wordpress username.
                  blog_pass:
                      Wordpress password.
                  post_title:
                      Title of the new post.
                  post_categories (optional):
                      List of the post's category names (they must exist).
                  post_keywords (optional):
                      List of keyword tags.
                  post_publish (optional):
                      1=Publish. 0=Draft. Default is 0.
                  post_body_exporter (optional):
                      An html excerpt exporter. Specify its options in
                      the config file as normal. Default is
                      "transcript_html".
  :raises: ExporterError, xmlrpclib.Fault, xmlrpclib.ProtocolError
  """
  missing_options = [o for o in ["xmlrpc_url","blog_user","blog_pass","post_title"] if (not options[ns+o])]
  if (len(missing_options) > 0):
    logging.error("Required exporter options weren't provided: %s." % ", ".join(missing_options))
    raise common.ExporterError("Exporter failed.")

  blog_id = 0
  if (ns+"blog_id" in options and options[ns+"blog_id"]):
    blog_id = options[ns+"blog_id"]

  post_catnames = []
  if (ns+"post_categories" in options and options[ns+"post_categories"]):
    post_catnames = options[ns+"post_categories"]

  post_tags = []
  if (ns+"post_tags" in options and options[ns+"post_tags"]):
    post_tags = options[ns+"post_tags"]

  post_publish = 0
  if (ns+"post_publish" in options and options[ns+"post_publish"]):
    post_publish = 1

  body_exporter_name = "transcript_html"
  if (ns+"post_body_exporter" in options and options[ns+"post_body_exporter"]):
    body_exporter_name = options[ns+"post_body_exporter"]


  exporters_pkg = __import__("lib.exporters", globals(), locals(), [body_exporter_name])
  exporter_mod = getattr(exporters_pkg, body_exporter_name)
  write_func = getattr(exporter_mod, "write_snarks")

  post_body = ""
  with contextlib.closing(StringIO.StringIO()) as buf:
    write_func(buf, snarks, show_time, options)
    buf.seek(0)
    post_body = buf.read()
    post_body = re.sub("\r\n?", "\n", post_body)
  if (not post_body):
    logging.error("Exporter for post body, %s, returned nothing." % body_exporter_name)
    raise common.ExporterError("Exporter failed.")

  server = xmlrpclib.ServerProxy(options[ns+"xmlrpc_url"])
  if (server.demo.addTwoNumbers(1,2) != 3):
    logging.error("Wordpress server answered incorrectly when asked what 1+2 was!")
    raise common.ExporterError("Exporter failed.")

  available_methods = server.mt.supportedMethods()
  required_methods = ["metaWeblog.getCategories", "metaWeblog.newPost"]
  missing_methods = [m for m in required_methods if m not in available_methods]
  if (len(missing_methods) > 0):
    logging.error("Wordpress server doesn't support these RPC methods: %s." % ", ".join(missing_methods))
    raise common.ExporterError("Exporter failed.")

  available_categories = server.metaWeblog.getCategories(blog_id, options[ns+"blog_user"], options[ns+"blog_pass"])
  available_catnames = [c['categoryName'] for c in available_categories]
  missing_catnames = [c for c in post_catnames if c not in available_catnames]
  if (len(missing_catnames) > 0):
    logging.error("These categories don't exist on the server: %s." % ", ".join(missing_catnames))
    raise common.ExporterError("Exporter failed.")

  content = {"title":options[ns+"post_title"], "description":post_body, "categories":post_catnames, "mt_keywords":post_tags}

  try:
    post_id = int(server.metaWeblog.newPost(blog_id, options[ns+"blog_user"], options[ns+"blog_pass"], content, post_publish))
    logging.info("Successfully created new post #%s." % post_id)
  except (xmlrpclib.Fault) as err:
    logging.error("Fault while posting (%d): %s" % (err.faultCode, err.faultString))
    raise common.ExporterError("Exporter failed.")
