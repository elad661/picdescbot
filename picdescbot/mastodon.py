# coding=utf-8
# picdescbot: a tiny twitter/tumblr bot that tweets random pictures from wikipedia and their descriptions
# this file implements Mastodon-related functionality
# Copyright (C) 2017 Federico Mena Quintero <federico@gnome.org>

# This uses Mastodon.py: https://pypi.python.org/pypi/Mastodon.py/1.0.5
# Documentation for that: https://mastodonpy.readthedocs.io/en/latest/

from mastodon import Mastodon

class Client(object):
    name = "mastodon"

    # FIXME: Note how
    # https://mastodonpy.readthedocs.io/en/latest/#app-registration-and-user-authentication
    # has the code bit to generate our mastodon-clientcred.txt.  We
    # don't do this here; do it by hand!
    #
    # Mastodon.create_app("picdescbot",
    #                     scopes       = ["write"],    # no read or follow
    #                     api_base_url = "https://botsin.space",
    #                     to_file      = "mastodon-clientcred.txt")
    #

    def __init__(self, config):
        # FIXME: pull this out of `config`
        self.mastodon = Mastodon(client_id = "mastodon-clientcred.txt")

        # FIXME: pull these out of `config`
        self.access_token = mastodon.log_in("username@example.com",
                                            "supersecretpassword")

    def send(self, picture):
        filename = picture.url.split('/')[-1]
        data = picture.download_picture()

        posted_pic_ids = self.mastodon.media_post (filename)

        self.mastodon.status_post (picture.caption,
                                   sensitive=True,
                                   media_ids=posted_pic_ids)
