#!/usr/bin/python3
# coding=utf-8
# picdescbot: a tiny twitter bot that tweets random pictures from wikipedia and their descriptions
# Copyright (C) 2016 Elad Alfassa <elad@fedoraproject.org>

from __future__ import unicode_literals, absolute_import, print_function

import argparse
import configparser
import os.path
import picdescbot.common
import picdescbot.logger
import picdescbot.tumblr
import picdescbot.twitter
import sys
import tweepy


def main():
    if sys.version_info.major < 3:
        print("This program does not support python2", file=sys.stderr)
        return

    # Start boring setup stuff (config file handling, etc)

    parser = argparse.ArgumentParser(description='Tweets pictures from wikipedia')
    parser.add_argument('config', metavar='config', nargs='?', type=str,
                        default=None, help='Path to config file')
    parser.add_argument('--manual', action="store_true")
    parser.add_argument('--tumblr-only', action="store_true")
    parser.add_argument('--disable-tag-blacklist', action="store_true")
    parser.add_argument('--wikimedia-filename', nargs='?', type=str,
                        default=None, help='Describe the specified picture from wikimedia, instead of a random one')
    args = parser.parse_args()
    config_file = "config.ini"
    if args.config is not None:
        config_file = os.path.expanduser(args.config)

    config = configparser.ConfigParser()
    config.read(config_file)

    if not args.tumblr_only:
        if (not config.has_section('twitter') or not
                config.has_option('twitter', 'consumer_key') or not
                config.has_option('twitter', 'consumer_secret')):

            print("You'll need to get a consumer key and a consumer secret" +
                  "from https://dev.twitter.com/apps")
            key = input('Enter twitter consumer key: ')
            secret = input('Enter twitter consumer secret: ')
            if not config.has_section('twitter'):
                config.add_section('twitter')
            config.set('twitter', 'consumer_key', key)
            config.set('twitter', 'consumer_secret', secret)
            with open(config_file, 'w') as f:
                config.write(f)
        consumer_key = config['twitter']['consumer_key']
        consumer_secret = config['twitter']['consumer_secret']

        # twitter auth stuff
        auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
        if (config.has_option('twitter', 'token') and
                config.has_option('twitter', 'token_secret')):

            auth.set_access_token(config['twitter']['token'],
                                  config['twitter']['token_secret'])
        else:
            print("Please authenticate with twitter:")
            print(auth.get_authorization_url())
            code = input('Enter authentication code from twitter: ').strip()
            auth.get_access_token(verifier=code)
            config.set('twitter', 'token', auth.access_token)
            config.set('twitter', 'token_secret', auth.access_token_secret)
            with open(config_file, 'w') as f:
                config.write(f)

    if (not config.has_section('mscognitive') or not
            config.has_option('mscognitive', 'api_key') or not
            config.has_option('mscognitive', 'endpoint')):
        apikey = input("Please enter your Microsoft Computer Vision API Key:")
        if not config.has_section('mscognitive'):
            config.add_section('mscognitive')
        config.set('mscognitive', 'api_key', apikey)
        endpoint = input("Please provide the endpoint for the Computer Vision API:")
        config.set('mscognitive', 'endpoint', endpoint)
        with open(config_file, 'w') as f:
            config.write(f)
    else:
        apikey = config['mscognitive']['api_key']
        endpoint = config['mscognitive']['endpoint']

    # end boring setup stuff

    if args.disable_tag_blacklist:
        picdescbot.common.tags_blacklist = {}
        args.manual = True  # less filtering means manual mode is mandatory

    cvapi = picdescbot.common.CVAPIClient(apikey, endpoint)
    if args.tumblr_only and not config.has_section('tumblr'):
        print('tumblr is not configured')
        print("You'll neeed the following fields: ")
        print("consumer_key, consumer_secret, token, token_secret, blog_id")
        return

    log = picdescbot.logger.get('main')

    providers = []
    if config.has_section('tumblr'):
        providers.append(picdescbot.tumblr.Client(config['tumblr']))

    if not args.tumblr_only:
        providers.append(picdescbot.twitter.Client(config['twitter']))

    post = False
    while not post:
        result = cvapi.get_picture_and_description(args.wikimedia_filename)
        if args.manual:
            action = None
            print(result.url)
            print(result.caption)
            while action not in ['y', 'n']:
                action = input("Post this? [y/n]: ")
            if action == "y":
                post = True
        else:
            post = True

    for provider in providers:
        status_id = provider.send(result)
        log.info("Sent {0}: {1} ({2})".format(provider.name, status_id,
                                              result.caption))

if __name__ == "__main__":
    main()
