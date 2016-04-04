#!/usr/bin/python3
# coding=utf-8
# picdescbot: a tiny twitter bot that tweets random pictures from wikipedia and their descriptions
# Copyright (C) 2016 Elad Alfassa <elad@fedoraproject.org>

from __future__ import unicode_literals, absolute_import, print_function

from wordfilter import Wordfilter
import json
import re
import requests
import time
import tweepy
import configparser
import argparse
import os.path
import sys
from io import BytesIO

MEDIAWIKI_API = "https://commons.wikimedia.org/w/api.php"
CVAPI = "https://api.projectoxford.ai/vision/v1.0/analyze"

HEADERS = {"User-Agent":  "picdescbot, http://github.com/elad661/picdescbot"}

supported_formats = re.compile('\.(png|jpe?g|gif)$', re.I)
word_filter = Wordfilter()
word_filter.add_words(['nazi'])  # I really don't want the bot to show this kind of imagery!


def get_random_picture():
    """Get a random picture from Wikimedia Commons.
    Returns None when the result is bad"""

    params = {"action": "query",
              "generator": "random",
              "grnnamespace": "6",
              "prop": "imageinfo",
              "iiprop": "url|size|extmetadata|mediatype",
              "iiurlheight": "1080",
              "format": "json"}
    response = requests.get(MEDIAWIKI_API,
                            params=params,
                            headers=HEADERS).json()
    page = list(response['query']['pages'].values())[0]  # This API is ugly
    imageinfo = page['imageinfo'][0]
    extra_metadata = imageinfo['extmetadata']

    # We got a picture, now let's verify we can use it.
    if word_filter.blacklisted(page['title']):  # Check file name for bad words
        print('badword ' + page['title'])
        return None
    # Check picture title for bad words
    if word_filter.blacklisted(extra_metadata['ObjectName']['value']):
        print('badword ' + extra_metadata['ObjectName']['value'])
        return None
    # Check restrictions for more bad words
    if word_filter.blacklisted(extra_metadata['Restrictions']['value']):
        print('badword ' + extra_metadata['ObjectName']['value'])
        return None

    # Now check that the file is useable
    if imageinfo['mediatype'] != "BITMAP":
        return None

    # Make sure the image is big enough
    if imageinfo['width'] <= 50 or imageinfo['height'] <= 50:
        return None

    if not supported_formats.search(imageinfo['url']):
        return None
    else:
        return imageinfo


def describe_picture(apikey, url):
    "Get description for a picture using Microsoft Cognitive Services"
    params = {'visualFeatures': 'Description,Adult'}
    json = {'url': url}
    headers = {'Content-Type': 'application/json',
               'Ocp-Apim-Subscription-Key': apikey}

    result = None
    retries = 0

    while retries < 15 and not result:
        response = requests.post(CVAPI, json=json, params=params,
                                 headers=headers)
        if response.status_code == 429:
            print ("Message: %s" % (response.json()))
            if retries < 15:
                time.sleep(2)
                retries += 1
            else:
                print('Error: failed after retrying!')

        elif response.status_code == 200 or response.status_code == 201:

            if 'content-length' in response.headers and int(response.headers['content-length']) == 0:
                result = None
            elif 'content-type' in response.headers and isinstance(response.headers['content-type'], str):
                if 'application/json' in response.headers['content-type'].lower():
                    result = response.json() if response.content else None
                elif 'image' in response.headers['content-type'].lower():
                    result = response.content
        else:
            print("Error code: %d" % (response.status_code))
            print("url: %s" % url)
            print(response.json())
            retries += 1
            time.sleep(10 + retries*3)

    return result


def get_picture_and_description(apikey, max_retries=20):
    "Get a picture and a description. Retries until a usable result is produced or max_retries is reached."
    pic = None
    retries = 0
    while retries <= max_retries:  # retry max 20 times, until we get something good
        while pic is None:
            pic = get_random_picture()
            if pic is None:
                # We got a bad picture, let's wait a bit to be polite to the API server
                time.sleep(1)
        url = pic['url']
        # Use a scaled-down image if the original is too big
        if pic['size'] > 4000000:
            url = pic['thumburl']

        description = describe_picture(apikey, url)
        if description is not None:
            if not description['adult']['isAdultContent']:  # no nudity and such
                if len(description['description']['captions']) > 0:
                    caption = description['description']['captions'][0]['text']
                    if not word_filter.blacklisted(caption):
                        return caption, url
                    else:
                        print("caption discarded due to word filter: " +
                              caption)
                else:
                    print("No caption for url: {0}".format(url))
            else:
                print("Adult content. Discarded.")
                print(url)
                print(description)
        retries += 1
        print("Not good, retrying...")
        pic = None
        time.sleep(3)  # sleep to be polite to the API servers

    raise Exception("Maximum retries exceeded, no good picture")


def download_picture(url):
    "Returns a BytesIO object for an image URL"
    retries = 0
    picture = None
    print("downloading " + url)
    while retries <= 20:
        if retries > 0:
            print('Trying again...')
        response = requests.get(url, headers=HEADERS)
        if response.status_code == 200:
            picture = BytesIO(response.content)
            return picture
        else:
            print("Fetching picture failed: " + response.status_code)
            retries += 1
            time.sleep(1)
    raise Exception("Maximum retries exceeded when downloading a picture")


def main():
    if sys.version_info.major < 3:
        print("This program does not support python2", file=sys.stderr)
        return

    # Start boring setup stuff (config file handling, etc)

    parser = argparse.ArgumentParser(description='Tweets pictures from wikipedia')
    parser.add_argument('config', metavar='config', nargs='?', type=str,
                        default=None, help='Path to config file')
    parser.add_argument('--manual', action="store_true")
    args = parser.parse_args()
    config_file = "config.ini"
    if args.config is not None:
        config_file = os.path.expanduser(args.config)

    config = configparser.ConfigParser()
    config.read(config_file)
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
    consumer_key = config.get('twitter', 'consumer_key')
    consumer_secret = config.get('twitter', 'consumer_secret')

    # twitter auth stuff
    auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
    if (config.has_option('twitter', 'token') and
            config.has_option('twitter', 'token_secret')):

        auth.set_access_token(config.get('twitter', 'token'),
                              config.get('twitter', 'token_secret'))
    else:
        print("Please authenticate with twitter:")
        print(auth.get_authorization_url())
        code = input('Enter authentication code from twitter: ').strip()
        auth.get_access_token(verifier=code)
        config.set('twitter', 'token', auth.access_token)
        config.set('twitter', 'token_secret', auth.access_token_secret)
        with open(config_file, 'w') as f:
            config.write(f)

    twitter = tweepy.API(auth)

    if (not config.has_section('mscognitive') or not
            config.has_option('mscognitive', 'api_key')):
        apikey = input("Please enter your Microsoft Computer Vision API Key:")
        if not config.has_section('mscognitive'):
            config.add_section('mscognitive')
        config.set('mscognitive', 'api_key', apikey)
        with open(config_file, 'w') as f:
            config.write(f)
    else:
        apikey = config.get('mscognitive', 'api_key')

    # end boring setup stuff

    tweet = False
    while not tweet:
        description, picurl = get_picture_and_description(apikey)
        if args.manual:
            action = None
            print(picurl)
            print(description)
            while action not in ['y', 'n']:
                action = input("Tweet this? [y/n]: ")
            if action == "y":
                tweet = True
        else:
            tweet = True

    # Download picture
    picture = download_picture(picurl)
    print(description, picurl)
    status = twitter.update_with_media(filename=picurl.split('/')[-1],
                                       status=description,
                                       file=picture)
    print("Tweeted: {0} ({1})".format(status.id, description))

if __name__ == "__main__":
    main()
