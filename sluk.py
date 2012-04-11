#!/usr/bin/python
# -*- mode: Python; encoding: utf-8; indent-tabs-mode: nil; tab-width: 2 -*-

import ConfigParser
import sys
import os
import time
import socket
from email.mime.text import MIMEText
from email.utils import formatdate
import json
import commands
import feedparser
import fileinput

# Run parsed data through HTML Tidy/uTidy in order to make sluk not
# barf on slightly invalid feeds.
feedparser.TIDY_MARKUP=1

# initialize user config
conf = ConfigParser.ConfigParser()

##################################################
# Function definitions

def usage(head=True):
  if head:
    print "Sluk rss feed message delivery"
  print """
Usage: sluk <command>

Available commands:

  add <name> <url>   Add feed.
  update             Update all feeds.
  remove <name>      Remove the feed named <name>.
  search <query>     Search the feed collection for feeds with nickname
                     or URL similar to <query>.
  help               This help message.
"""

def print_optionally(string):
  "print the given string if the config option quiet is false or not set"
  if not conf.has_option("conf", "quiet") or not conf.getboolean("conf", "quiet"):
    print string

def create_unique_filename():
  "Create a unique maildir-style filename. See http://cr.yp.to/proto/maildir.html"
  filename = repr(time.time()) + "_" + str(os.getpid()) + "." + socket.gethostname() + ":2,"
  return filename

def is_feed(feed):
  "True if argument is a valid feed, false otherwise."
  feed_version = feedparser.parse(feed).version
  return not (feed_version == "" or feed_version == None)


def initialize_config():
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


def parse_feed_line(feed):
  """return a 3-tuple of nick, feed, bodyfilter, where all are None if it was a comment line,
  and where bodyfilter or nick are None if omitted."""
  if not feed or feed[0] == "#":
    return (None, None, None)
    
  split      = feed.split()
  nick       = None
  bodyfilter = None

  if len(split) > 1:
    feed = split[1]
    nick = split[0].decode("utf-8")
    
  if len(split) > 2:
    bodyfilter = split[2]

  return (nick, feed, bodyfilter)
  
def search(query):
  try:
    from Levenshtein import ratio as ratio
  except ImportError:
    print "Error: You need the Levenshtein module (python-levenshtein in Debian) to search."
    exit(1)

  def sort_of_similar(a, b):
    if not a == None and not b == None:
      return ratio(a.encode("utf-8"), b.encode("utf-8")) > 0.50

  with open(conf.get("conf", "feed_list")) as f:
    for line in f:
      nick, url, bodyfilter = parse_feed_line(line)
      if sort_of_similar(query, nick) or sort_of_similar(query, url):
        print nick, url
      

def remove_feed(name):
  found = False
  lines = []
  with open(conf.get("conf", "feed_list")) as f:
    for line in f:
      nick, url, bodyfilter = parse_feed_line(line)
      if nick == name:
        print "Removed feed \"%s\" in %s." % (nick, conf.get("conf", "feed_list"))
        found = True
        continue
      else:
        lines.append(line)
  if found:
    with open(conf.get("conf", "feed_list"), 'w') as f:
      f.writelines(lines)
  else:
    print "No feed named \"%s\" found in %s." % (name, conf.get("conf", "feed_list"))
  
def add_feed(name, url):
  if not is_feed(url):
    print "url is invalid."
    exit(1)

  feed_list = os.path.expanduser(conf.get("conf", "feed_list"))

  if not os.path.exists(feed_list):
    f = open(feed_list, 'w').close()

  with open(feed_list, 'r') as f:
    for line in f:
      line = line.strip(' \n')
      feed = line.split(' ')
      if name == feed[0]:
        print "Feed '%s' already in collection (%s)." % (name,url)
        exit(1)
      if url == feed[1]:
        print "Feed '%s' already in collection as '%s'." % (url,name)
        exit(1)
  f.close()
  f = open(feed_list, 'a')
  f.write("%s %s\n" % (name,url))
  print "Feed '%s' added to collection." % name
  f.close()

def update_feeds():
  "update all feeds"
  # initialize cache
  try:
    cache = json.loads(open(conf.get("conf", "cache")).read())
  except IOError, ValueError:
    cache = {}

  # Simple string concatenation instead of os.path.join(),
  # we want "cache_entries", not "cache/_entries" !
  cache_entries_file = conf.get("conf", "cache") + "_entries"

  try:
    # "with" ensures everything is nicely cleaned up afterwards
    # (closed, released, ...) without needing specific "finally:" code.
    with open(cache_entries_file, 'r') as f:
      cache_entries = f.read().split("\n")
  except IOError:
    cache_entries = ""

  cache_entries_new = ""

  entries = []

  for feed in open(conf.get("conf", "feed_list")).read().split("\n"):
    
    nick, feed, bodyfilter = parse_feed_line(feed)

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
      print("parsing %s failed!" % nick)
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

      # If lnk is NOT in cache_entries, append it to
      # cache_entries_new and proceed as usual.
      # Otherwise, drop this entry and start processing the next.
      if not lnk.encode(parsed.encoding) in cache_entries:
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

  print_optionally("updating cache file: " + conf.get("conf", "cache"))
  cache_file = open(conf.get("conf", "cache"), "w")
  cache_file.write(json.dumps(cache))
  cache_file.close()

  try:
    print_optionally("I: Updating entries cache: '%s'" % cache_entries_file)
    with open(cache_entries_file, 'a') as f:  # append, not write
      f.write(cache_entries_new.encode(parsed.encoding))
  except IOError:
    print_optionally("E: Failed writing to entries cache file: '%s'" % cache_entries_file)

##################################################
# Main

if len(sys.argv) == 1:
  usage()
  exit(1)

if sys.argv[1] == 'add':
  if len(sys.argv) < 4:
    print "Add: must specify both name and url."
    print "See '%s help' for more info." % (os.path.basename(sys.argv[0]))
    exit(1)
  name = sys.argv[2]
  url = sys.argv[3]
  initialize_config()
  add_feed(name, url)
elif sys.argv[1] == 'remove':
  if len(sys.argv) < 3:
    print "Remove: must specify name."
    print "See '%s help' for more info." % (os.path.basename(sys.argv[0]))
    exit(1)
  name = sys.argv[2]
  initialize_config()
  remove_feed(name)
elif sys.argv[1] == 'update':
  initialize_config()
  update_feeds()

elif sys.argv[1] == 'help':
  usage()
  exit()

elif sys.argv[1] == 'search':
  # make function here. Use Levenshtein. Catch import errors.
  initialize_config()
  search(" ".join(sys.argv[2:]))
  exit()

else:
  print "Unknown command '%s'." % (sys.argv[1])
  print "See '%s help' for more info." % (os.path.basename(sys.argv[0]))
  usage(False)
  exit(1)
