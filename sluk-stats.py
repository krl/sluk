#!/usr/bin/python2.6
# -*- coding: utf-8 -*-
# A short script to provide some statistics over my feed-reading
# practices. Feel free to modify it and spread it as you please.
#
# Of course, you may want to replace my queries and base path
# variables, as they probably don't apply to you.

import os.path
import notmuch

rek = notmuch.Database().create_query("tag:feeds and tag:rek")
feeds = notmuch.Database().create_query("tag:feeds")

base = os.path.expanduser("~/inmail/sluk/")

results = dict()

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

def ratio_of_messages (a, b):
    void, a_stats = a
    void, b_stats = b
    return float(a_stats[0])/float(a_stats[1]), float(b_stats[0])/float(b_stats[1])

for s in sorted(results.iteritems(),
             cmp=lambda x, y: cmp(*ratio_of_messages(x, y)), reverse=True):
    name, stats = s
    print "»%s«: %d of %d (%.2f%%)" % (name, stats[0], stats[1], 100*float(stats[0])/float(stats[1]))

print "" 

print "Percent recommended posts: %.2f%%." % (100*float(rek.count_messages())/float(feeds.count_messages()))
