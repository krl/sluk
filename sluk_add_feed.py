#!/usr/bin/python
# -*- encoding:utf-8 -*-
# A small hack to add a feed to your sluk collection.

import ConfigParser, feedparser, sys, os

conf = ConfigParser.ConfigParser()
conf.readfp(open(os.path.expanduser('~/.slukrc')))

feed_list = conf.get("conf", "feed_list")

def is_feed(feed):
    "True if argument is a valid feed, false otherwise."
    feed_version = feedparser.parse(feed).version
    return not (feed_version == "" or feed_version == None)

def print_usage_help():
    "Print the usage help to stdout."
    help = "Usage: sluk_add_feed.py <feed URL>.\nThe feed URL needs to be a valid feed."
    print help

# Test if the argument is sane, otherwise give usage help.
if len(sys.argv) != 2 or not is_feed(sys.argv[1]):
    print_usage_help()
elif not sys.argv[1] in open(feed_list).read().split("\n"):
    f = open(feed_list, 'a')
    f.write(sys.argv[1] + "\n")
else:
    print "Feed %s already in collection!" %  sys.argv[1]
