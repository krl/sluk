#!/usr/bin/python
# -*- mode: Python; encoding: utf-8; indent-tabs-mode: nil; tab-width: 2 -*-

import ConfigParser
import os
import time
import socket
from email.mime.text import MIMEText
from email.utils import formatdate
import json
import commands
import feedparser

# function definitions
def print_optionally(string):
  "print the given string if the config option quiet is false or not set"
  if not conf.has_option("conf", "quiet") or not conf.getboolean("conf", "quiet"):
    print string

def create_unique_filename():
  "Create a unique maildir-style filename. See http://cr.yp.to/proto/maildir.html"
  filename = repr(time.time()) + "_" + str(os.getpid()) + "." + socket.gethostname() + ":2,"
  return filename

# initialize user config
conf = ConfigParser.ConfigParser()

if os.getenv("SLUK_CONFIG"):
  config_file = os.path.expanduser(os.path.expandvars(os.getenv("SLUK_CONFIG")))
else:
  config_file = os.path.expanduser("~/.slukrc")

try:
  conf.readfp(open(config_file))
  print_optionally("I: Using config file '%s'" % config_file)
except IOError:
  print("E: Config file not found '%s'" % config_file)
  exit(1)

# initialize cache
if not conf.has_option("conf", "cache_feeds"):
  cache_feeds_file = conf.get("conf", "cache")
else:
  cache_feeds_file = conf.get("conf", "cache_feeds")

if not conf.has_option("conf", "cache_entries"):
  cache_entries_file = conf.get("conf", "cache") + "_entries"
else:
  cache_entries_file = conf.get("conf", "cache_entries")

try:
  with open(cache_feeds_file, 'r') as f:
    print_optionally("I: Using feeds cache file: '%s'" % cache_feeds_file)
    cache = json.loads(f.read())
except IOError, ValueError:
  print_optionally("E: Failed loading feeds cache file: '%s'" % cache_feeds_file)
  cache = {}

try:
  with open(cache_entries_file, 'r') as f:
    print_optionally("I: Using entries cache file: '%s'" % cache_entries_file)
    cache_entries = f.read().split("\n")
except IOError:
  print_optionally("E: Failed loading entries cache file: '%s'" % cache_entries_file)
  cache_entries = ""

cache_entries_new = ""

entries = []

for feed in open(conf.get("conf", "feed_list")).read().split("\n"):

  # means commented out
  if not feed or feed[0] == "#": continue

  split      = feed.split()
  nick       = None
  bodyfilter = None

  if len(split) > 1:
    feed = split[1]
    nick = split[0].decode("utf-8")

  if len(split) > 2:
    bodyfilter = split[2]


  if nick:
    print_optionally(nick + " " + feed)
  else:
    print_optionally(feed)

  if feed not in cache:
    cache[feed] = {"etag": None, "modified": None}

  try:
    parsed = feedparser.parse(feed,
                              etag     = cache[feed]["etag"],
                              # needs time in tuple form
                              modified = cache[feed]["modified"] and \
                                time.gmtime(cache[feed]["modified"]))
  except:
    print_optionally("parsing failed!")
    continue

  if 'status' in parsed and parsed.status == 304:
    print_optionally(" - server says not changed")
    continue

  cache[feed]["etag"]     = parsed.etag if hasattr(parsed, "etag") else None
  cache[feed]["modified"] = time.mktime(parsed.modified) if hasattr(parsed, "modified") else None

  # count
  num_written = 0

  for entry in parsed.entries:

    lnk = ""
    if 'link' not in entry:
      if 'enclosures' in entry and 'href' in entry.enclosures[0]:
        lnk = entry.enclosures[0].href
      else:
        print_optionally("Warning! Skipping entry in feed %s that lacks both href enclosure and entry element!" % feed)
        continue # If the entry has neither link nor href element, it's clearly not a feed -- skip it.
    else:
      lnk = entry.link

    if not lnk in cache_entries:
      cache_entries_new += lnk + "\n"
    else:
      continue

    directory = os.path.join(conf.get("conf", "messages"), (nick or ""))
    if not os.path.exists(directory):
      os.makedirs(directory)

    # we like unique filenames
    path = ""
    while not path or os.path.exists(path):
      path = os.path.join(directory, create_unique_filename())

    # this should never ever occur (although never say never ever),
    # but leave it here anyway since removing it would alter indentation
    # for about 40 lines, and we don't like obese patches for simple changes
    if os.path.exists(path):
      print("E: File already exists: '%s'  -- Skipping..." % path)

    else:
      # content is not always in feed, use summary
      if "content" in entry:
        content = entry.content[0].value
      elif "summary" in entry:
        content = entry.summary
      else:
        content = lnk

      try:
        content   = content.encode(parsed.encoding)
        feed_name = parsed['feed']['title'].encode(parsed.encoding)
        title     = entry['title'].encode(parsed.encoding)
        link      = lnk.encode(parsed.encoding)
      except UnicodeEncodeError:
        print_optionally("error decoding entry: " + path)
        continue
      except KeyError:
        print_optionally("error parsing entry: " + path)
        continue

      if bodyfilter:
        content = commands.getoutput(conf.get("filters", bodyfilter).replace("{url}", link))

      # create text/html message only
      msg = MIMEText(content, "html")

      msg['Subject'] = title
      msg['From']    = feed_name + " <sluk@" + os.uname()[1] + ">"
      msg['To']      = "sluk@" + os.uname()[1]

      if hasattr(entry, "updated_parsed"):
        msg['Date']  = formatdate(time.mktime(entry.updated_parsed))
      else:
        msg['Date']  = formatdate(time.time())

      msg['X-Entry-URL'] = msg['Message-ID'] = link

      # write to file
      entries.append({"path": path,
                      "body": msg.as_string()})

      num_written += 1

  if num_written == 1:
    print_optionally(" - 1 new entry")
  if num_written > 1:
    print_optionally(" - %i new entries" % num_written)

# write files

for x in entries:
  print_optionally("writing " + x['path'])
  message_file = open(x['path'], "w")
  message_file.write(x['body'])
  message_file.close()

# update cache

try:
  print_optionally("I: Updating feeds cache: '%s'" % cache_feeds_file)
  with open(cache_feeds_file, 'w') as f:
    f.write(json.dumps(cache))
except IOError:
  print_optionally("E: Failed writing to feeds cache file: '%s'" % cache_feeds_file)

try:
  print_optionally("I: Updating entries cache: '%s'" % cache_entries_file)
  with open(cache_entries_file, 'a') as f:
    f.write(cache_entries_new)
except IOError:
  print_optionally("E: Failed writing to entries cache file: '%s'" % cache_entries_file)
