# coding=utf-8
# picdescbot: a tiny twitter/tumblr/mastodon bot that tweets random pictures
# from wikipedia and their descriptions
# this file implements mastodon-related functionality
# Copyright (C) 2016 Elad Alfassa <elad@fedoraproject.org>
# Copyright (C) 2018 Elsie Powell <me@elsiepowell.com>

import mimetypes
import time
from mastodon import Mastodon, MastodonError
from . import logger


class Client(object):
    name = "mastodon"

    def __init__(self, config):
        self.api = Mastodon(
            access_token=config['access_token'],
            api_base_url=config['base_uri'],
        )
        self.log = logger.get(__name__)

    def send(self, picture):
        "Send a toot. `picture` is a `Result` object from `picdescbot.common`"
        retries = 0
        status = None
        filename = picture.url.split('/')[-1]
        mime_type = mimetypes.guess_type(filename)
        data = picture.download_picture()
        try:
            while retries < 3 and not status:
                if retries > 0:
                    self.log.info('retrying...')
                    data.seek(0)
                try:
                    text = '\n\n'.join((picture.caption, picture.source_url))
                    media = self.api.media_post(data, mime_type=mime_type)
                    status = self.api.status_post(text, media_ids=media)
                except MastodonError as e:
                    self.log.error("Error when sending toot: %s" % e)
                    retries += 1
                    if retries >= 3:
                        raise
                    else:
                        time.sleep(5)
        finally:
            data.close(really=True)
        return status['id']
