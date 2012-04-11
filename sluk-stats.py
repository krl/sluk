#!/usr/bin/python2.6
# -*- coding: utf-8 -*-
# A short script to provide some statistics over my feed-reading
# practices. Feel free to modify it and spread it as you please.
#
# Of course, you may want to replace my queries and base path
# variables, as they probably don't apply to you.

import os.path, notmuch, operator, ConfigParser

conf = ConfigParser.ConfigParser()

# CUSTOMIZE THESE VARIABLES TO YOUR LIKING
rek = notmuch.Database().create_query("tag:feeds and tag:rek")
feeds = notmuch.Database().create_query("tag:feeds")
config_file = os.path.expanduser("~/.slukrc")

conf.readfp(open(config_file))
base = os.path.expanduser(conf.get("conf", "messages"))

registered_feeds = [a.split(' ')[0] for a in
                    open(conf.get("conf", "feed_list")).read().split('\n')]

results = dict()
no_reks = dict()

for a in rek.search_messages():
    feedname = os.path.dirname(a.get_filename()).replace(base, "")
    if not feedname  in results:
        results[feedname] = [1, 0]
    else:
        results[feedname][0] += 1

for a in feeds.search_messages():
    feedname = os.path.dirname(a.get_filename()).replace(base, "")
    if feedname  in results:
        results[feedname][1] += 1
    elif feedname in no_reks:
        no_reks[feedname] += 1
    else:
        no_reks[feedname] = 1

def ratio_of_messages (a, b):
    void, a_stats = a
    void, b_stats = b
    return float(a_stats[0])/float(a_stats[1]), float(b_stats[0])/float(b_stats[1])


print "The following feeds had recommended posts (sorted by decending ratio of recommended/total posts):"
for s in sorted(results.iteritems(),
             cmp=lambda x, y: cmp(*ratio_of_messages(x, y)), reverse=True):
    name, stats = s
    if name in registered_feeds:
        print "    »%s«: %d of %d (%.2f%%)" % (name, stats[0], stats[1], 100*float(stats[0])/float(stats[1]))

print ""
print "The following feeds lacked any recommended posts:"

for s in sorted(no_reks.iteritems(), key=operator.itemgetter(1)):
    print "    »%s«: (%d posts)" % s
    
print ""

print "Percent recommended posts: %.2f%%." % (100*float(rek.count_messages())/float(feeds.count_messages()))
