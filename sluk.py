#!/usr/bin/python
# -*- encoding:utf-8 -*-

import ConfigParser, feedparser, os, time, json

from email.mime.text import MIMEText
from email.utils import formatdate
from hashlib import md5

# init conf object
conf = ConfigParser.ConfigParser()
conf.readfp(open(os.path.expanduser('~/.slukrc')))

# initialize cache
try:
  cache = json.loads(open(conf.get("conf", "cache")).read())
except IOError:
  cache = {}
except ValueError:
  cache = {}

for feed in open(conf.get("conf", "feed_list")).read().split("\n"):
  # some output
  print feed

  if not cache.has_key(feed):
    cache[feed] = {"etag": None, "modified": None}

  parsed = feedparser.parse(feed,
                            etag     = cache[feed]["etag"],
                            # needs tuple form time
                            modified = time.gmtime(cache[feed]["modified"]))

  if parsed.has_key('status') and parsed.status == 304:
    print " - server says not changed"
    continue

  cache[feed]["etag"]     = parsed.etag if hasattr(parsed, "etag") else None
  cache[feed]["modified"] = time.mktime(parsed.modified) if hasattr(parsed, "modified") else None

  # count
  num_written = 0

  for entry in parsed.entries:
    path = conf.get("conf", "messages") + entry.link.replace("/", "!")

    # python don't like long pathnames
    if len(path) > 256:
      path = conf.get("conf", "messages") + md5(path).hexdigest()

    # ignore updated feeds for now 
    # maybe TODO handle this in any way?
    if not os.path.exists(path):

      # content is not always in feed, use summary
      if entry.has_key("content"):
        content = entry.content[0].value
      else:
        content = entry.summary

      # create text/html message only
      msg = MIMEText(content.encode("utf-8"), "html")      

      msg['Subject'] = entry['title'].encode("utf-8")
      msg['From']    = parsed['feed']['title'].encode("utf-8") + " <sluk@" + os.uname()[1] + ">"
      msg['To']      = "sluk@" + os.uname()[1]
      if hasattr(entry, "updated_parsed"):
        msg['Date']    = formatdate(time.mktime(entry.updated_parsed))

      # write to file
      message_file = open(path, "w")
      message_file.write(msg.as_string())
      message_file.close()

      num_written += 1

  if num_written == 1:
    print " - 1 new entry"
  if num_written > 1:
    print " - %i new entries" % num_written

# update cache

cache_file = open(conf.get("conf", "cache"), "w")
cache_file.write(json.dumps(cache))
cache_file.close()
