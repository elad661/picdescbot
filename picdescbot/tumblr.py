# coding=utf-8
# picdescbot: a tiny twitter/tumblr bot that tweets random pictures from wikipedia and their descriptions
# this file implements tumblr-related functionality
# Copyright (C) 2016 Elad Alfassa <elad@fedoraproject.org>

from tumblpy import Tumblpy
from . import common

DEFAULT_PARAMS = {'type': 'photo', 'state': 'queue',
                  'native_inline_images': True}

TEMPLATE = "<h2><b>{description}</b></h2>" + \
           "<p><a href=\"https://picdescbot.tumblr.com/about\">" + \
           "about this bot</a>&nbsp;|&nbsp;" + \
           "<a href=\"{source}\">picture source</a></p>" + \
           "<p><i>this post is 100% computer-generated, including tags</i></p>"
DEFAULT_TAGS = ['picdescbot', 'bot']


class Client(object):
    name = "tumblr"

    def __init__(self, config):
        self.client = Tumblpy(config['consumer_key'], config['consumer_secret'],
                              config['token'], config['token_secret'])
        self.blog_id = config['blog_id']

    def send(self, picture):
        "Post a post. `picture` is a `Result` object from `picdescbot.common`"

        post_text = TEMPLATE.format(description=picture.caption,
                                    source=picture.source_url)

        # People asked me to add tags to the posts, but blindly adding them
        # is not good enough. I need to think of a way to use wordnik to filter
        # common adjectives or something. I also need to decide if I really want
        # to implement this request, because it might cause the bot's post
        # to appear as spam for people who simply follow some tags.

        # tag filtering:
        # for tag in picture.tags:
        #     if tag in tag_blacklist or common.word_filter.blacklisted(tag):
        #         picture.tags.remove(tag)

        tags = DEFAULT_TAGS  # + picture.tags

        params = {'caption': post_text,
                  'source': picture.url,
                  'tags': ','.join(tags)}
        params.update(DEFAULT_PARAMS)

        post = self.client.post("post", blog_url=self.blog_id,
                                params=params)
        return post['id']
