#!/usr/bin/python
# -*- encoding:utf-8 -*-

import ConfigParser
import feedparser
import os
import time
import json

from email.mime.text import MIMEText
from email.utils import formatdate
from hashlib import md5


# init conf object
conf = ConfigParser.ConfigParser()
conf.readfp(open(os.path.expanduser('~/.slukrc')))

def print_optionally(string):
  "print the given string if the config option quiet is false or not set"
  if not conf.has_option("conf", "quiet") or not conf.getboolean("conf", "quiet"):
    print string

# initialize cache
try:
  cache = json.loads(open(conf.get("conf", "cache")).read())
except IOError, ValueError:
  cache = {}

entries = []

for feed in open(conf.get("conf", "feed_list")).read().split("\n"):
  # some output
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

    path = os.path.join(conf.get("conf", "messages"), lnk.replace("/", "!"))

    # python don't like long pathnames
    if len(path) > 256:
      path = os.path.join(conf.get("conf", "messages"), md5(path).hexdigest())

    # ignore updated feeds for now 
    # maybe TODO handle this in any way?
    if not os.path.exists(path):

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

      # create text/html message only
      msg = MIMEText(content, "html")

      msg['Subject'] = title
      msg['From']    = feed_name + " <sluk@" + os.uname()[1] + ">"
      msg['To']      = "sluk@" + os.uname()[1]
      if hasattr(entry, "updated_parsed"):
        msg['Date']    = formatdate(time.mktime(entry.updated_parsed))
      msg['X-Entry-URL'] = link

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

cache_file = open(conf.get("conf", "cache"), "w")
cache_file.write(json.dumps(cache))
cache_file.close()
