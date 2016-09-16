# coding=utf-8
# picdescbot: a tiny twitter/tumblr bot that tweets random pictures from wikipedia and their descriptions
# this file implements twitter-related functionality
# Copyright (C) 2016 Elad Alfassa <elad@fedoraproject.org>

import time
import tweepy


class Client(object):
    name = "twitter"

    def __init__(self, config):
        auth = tweepy.OAuthHandler(config['consumer_key'],
                                   config['consumer_secret'])
        auth.set_access_token(config['token'], config['token_secret'])
        self.api = tweepy.API(auth)

    def send(self, picture):
        "Send a tweet. `picture` is a `Result` object from `picdescbot.common`"
        retries = 0
        status = None
        filename = picture.url.split('/')[-1]
        data = picture.download_picture()
        try:
            while retries < 3 and not status:
                if retries > 0:
                    print('retrying...')
                    data.seek(0)
                try:
                    status = self.api.update_with_media(filename=filename,
                                                        status=picture.caption,
                                                        file=data)
                except tweepy.TweepError as e:
                    print("Error when sending tweet: %s" % e)
                    retries += 1
                    if retries >= 3:
                        raise
                    else:
                        time.sleep(5)
        finally:
            data.close(really=True)
        return status.id
