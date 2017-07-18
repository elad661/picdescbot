# coding=utf-8
# picdescbot: a tiny twitter/tumblr bot that tweets random pictures from wikipedia and their descriptions
# this file implements tumblr-related functionality
# Copyright (C) 2016 Elad Alfassa <elad@fedoraproject.org>

from tumblpy import Tumblpy
import tumblpy.exceptions
import time
from . import common
from . import logger

DEFAULT_PARAMS = {'type': 'photo', 'state': 'queue',
                  'native_inline_images': True}

# using the goo.gl link in the template instead of the actual link, because
# tumblr on mobile doesn't show pages when linked with the actual link -
# it just sends the user to the blog's front page instead.
# The goo.gl redirect makes the tumblr app think it's an external website,
# and open it in the browser instead.

TEMPLATE = "<h2><b>{description}</b></h2>" + \
           "<p><a href=\"https://picdescbot.tumblr.com\">@picdescbot</a>" + \
           "&nbsp;|&nbsp;<a href=\"https://goo.gl/qLvF4K\">" + \
           "about this bot</a>&nbsp;|&nbsp;" + \
           "<a href=\"{source}\">picture source</a></p>" + \
           "<p><i>all text in this post is 100% computer-generated, including tags</i></p>"
DEFAULT_TAGS = ['picdescbot', 'bot']

# All kinds of tags that should be filtered from the bot's post
tag_blacklist = {'woman', 'black', 'white', 'man', 'body', 'large', 'tall',
                 'small', 'young', 'old', 'top', 'boy', 'girl'}


def filter_tags(tags):
    filtered = []
    for tag in tags:
        if tag not in tag_blacklist and not common.word_filter.blacklisted(tag):
            filtered.append(tag)
    return filtered


class Client(object):
    name = "tumblr"

    def __init__(self, config):
        self.client = Tumblpy(config['consumer_key'], config['consumer_secret'],
                              config['token'], config['token_secret'])
        self.blog_id = config['blog_id']
        self.log = logger.get(__name__)

    def send(self, picture):
        "Post a post. `picture` is a `Result` object from `picdescbot.common`"

        post_text = TEMPLATE.format(description=picture.caption,
                                    source=picture.source_url)

        tags = DEFAULT_TAGS + filter_tags(picture.tags)

        params = {'caption': post_text,
                  'source': picture.url,
                  'tags': ','.join(tags)}
        params.update(DEFAULT_PARAMS)

        retries = 0
        post = None
        while retries < 3 and post is None:
            if retries > 0:
                self.log.info('retrying...')
            try:
                post = self.client.post("post", blog_url=self.blog_id,
                                        params=params)
            except tumblpy.exceptions.TumblpyError as e:
                self.log.error("Error when sending tumblr post: %s" % e)
                retries += 1
                if retries >= 3:
                    raise
                else:
                    time.sleep(5)
        return post['id']
