# coding=utf-8
# picdescbot: a tiny twitter/tumblr bot that tweets random pictures from wikipedia and their descriptions
# this file contains common basic functionality of the bot, such as getting the picture and description
# Copyright (C) 2016-2017 Elad Alfassa <elad@fedoraproject.org>

from __future__ import unicode_literals, absolute_import, print_function

from wordfilter import Wordfilter
import json
import re
import requests
import time
import lxml.html
from . import logger
from io import BytesIO

log = logger.get("common")

MEDIAWIKI_API = "https://commons.wikimedia.org/w/api.php"
CVAPI = "https://api.projectoxford.ai/vision/v1.0/analyze"

HEADERS = {"User-Agent":  "picdescbot, http://github.com/elad661/picdescbot"}

supported_formats = re.compile('\.(png|jpe?g|gif)$', re.I)
word_filter = Wordfilter()

# I really don't want the bot to show this kind of imagery!
word_filter.add_words(['nazi', 'hitler', 'reich'])

# I can't trust Microsoft's algorithm to not be racist, so I should probably
# make the bot avoid posting images with the following words in them.
# I'm not using wordfilter here because it would over-filter in some cases.
extra_filter = {'ape', 'apes', 'monkey', 'monkeys'}

# Blacklisted phrases (instead of words) to blacklist certain phrases
# in the wikimedia description
blacklisted_phrases = {'comic strip', 'logo'}

# Blacklist some categories, just in case. These are matched on a substring
# basis, against the page's categories and the titles of the wikipages using
# the picture.
category_blacklist = ['september 11', 'hitler', 'nazi', 'antisemit', 'libel',
                      'apartheid', 'racism', 'lynching', 'cartoons',
                      'holocaust', 'stereotypes', 'flags', 'porn',
                      'homophobia', 'transphobia', 'logos',
                      'scans from google books', 'little nemo',
                      'stolperstein', 'songbird specimens', 'terror']

# Gender neutralization helps prevent accidental transphobic juxtapositions
# which can occur when CVAPI uses gendered words in the description, but their
# gender detection is wrong. Computers shouldn't try to detect gender, and
# always be neautral. You can't know someone's gender just by how they look!
gendered_words = {'woman': 'person',
                  'man': 'person',
                  'women': 'people',
                  'men': 'people',
                  'guy': 'person',
                  'boy': 'person',
                  'girl': 'person',
                  'boys': 'people',
                  'girls': 'people',
                  'lady': 'person',
                  'ladies': 'people',
                  'gentleman': 'person',
                  'gentlemen': 'people',
                  'female': '',
                  'male': '',
                  'she': 'they',
                  # It's probably more likely to say "woman and her phone" than
                  # "someone gives a phone to her", so their is probably better
                  # here. Would need more complex parsing to know for sure.
                  'her': 'their',
                  'hers': 'theirs',
                  'herself': 'themself',
                  'he': 'they',
                  'him': 'them',
                  # It's more likely to give "man and his phone" than "this
                  # phone is his", so "their" is better here than "theirs"
                  'his': 'their',
                  'himself': 'themself'}


def gender_neutralize(phrase):
    "Replace gendered words in the phrase with neutral ones"
    neutralized = []
    for word in phrase.lower().split():
        if word in gendered_words:
            word = gendered_words[word]
        if word != '':
            neutralized.append(word)
    neutralized = ' '.join(neutralized)
    if neutralized != phrase:
        log.info('Gender neutralized: "{0}" => "{1}"'.format(phrase, neutralized))
    return neutralized


tags_blacklist = {'text', 'screenshot', 'military uniform'}


def tag_blacklisted(tags):
    for tag in tags:
        if tag in tags_blacklist:
            return True
    return False


def is_blacklisted(caption):
    """ Check caption for forbidden words"""
    if "a suit and tie" in caption:
        return True
    if word_filter.blacklisted(caption):
        return True
    for word in caption.split():
        if word in extra_filter:
            return True
    return False


def remove_html_tags(text):
    """ Remove all HTML tags (and properties) from a string """
    return ' '.join(lxml.html.fromstring(text).itertext())


def log_discarded(url, reason, description=None):
    line = "Discarded {0} because of {1}".format(url, reason)
    if description is not None:
        line += ' - "{0}"'.format(description)
    log.warning(line)


def get_picture(filename=None):
    """Get a picture from Wikimedia Commons. A random picture will be returned if filename is not specified
    Returns None when the result is bad"""
    params = {"action": "query",
              "prop": "imageinfo|categories|globalusage",
              "iiprop": "url|size|extmetadata|mediatype",
              "iiurlheight": "1080",
              "format": "json"}
    if filename is None:
        params['generator'] = 'random'
        params['grnnamespace'] = '6'
    else:
        params['titles'] = 'File:%s' % filename

    response = requests.get(MEDIAWIKI_API,
                            params=params,
                            headers=HEADERS).json()
    page = list(response['query']['pages'].values())[0]  # This API is ugly
    imageinfo = page['imageinfo'][0]
    url = imageinfo['url']
    extra_metadata = imageinfo['extmetadata']

    # check that the file is actually a picture
    if imageinfo['mediatype'] != "BITMAP":
        return None

    # Make sure the picture is big enough
    if imageinfo['width'] <= 50 or imageinfo['height'] <= 50:
        return None

    # Make sure the format is supported
    if not supported_formats.search(url):
        return None

    # We got a picture, now let's verify we can use it.
    if word_filter.blacklisted(page['title']):  # Check file name for bad words
        log_discarded(url, 'badword in page title: "{0}"'.format(page['title']))
        return None
    # Check picture title for bad words
    if word_filter.blacklisted(extra_metadata['ObjectName']['value']):
        log_discarded(url, 'badword in picture title: "{0}"'.format(extra_metadata['ObjectName']['value']))
        return None
    # Check restrictions for more bad words
    if word_filter.blacklisted(extra_metadata['Restrictions']['value']):
        log_discarded(url, 'badword in restrictions: "{0}"'.format(extra_metadata['Restrictions']['value']))
        return None

    # Check file description for bad words
    if 'ImageDescription' in extra_metadata:
        cleaned_description = remove_html_tags(extra_metadata['ImageDescription']['value'])
        if word_filter.blacklisted(cleaned_description):
            log_discarded(url, 'badword in image description: "{0}"'.format(cleaned_description))
            return None

        for phrase in blacklisted_phrases:
            if phrase in cleaned_description.lower().strip():
                log_discarded(url, 'blacklisted phrase "{0}" found in description "{1}"'.format(phrase, cleaned_description))
                return None

    # The mediawiki API is awful, there's another list of categories which
    # is not the same as the one requested by asking for "categories".
    # Fortunately it's still in the API response, under extmetadata.

    extra_categories = extra_metadata['Categories']['value'].lower()

    for blacklisted_category in category_blacklist:
        for category in page['categories']:
            if blacklisted_category in category['title'].lower():
                log_discarded(url, 'blacklisted category "{0}"'.format(category['title']))
                return None

        if blacklisted_category in extra_categories:
            log_discarded(url, 'blacklisted category "{0}" (in extra)'.format(blacklisted_category))
            return None

    # if the picture is used in any wikipage with unwanted themes, we probably
    # don't want to use it.
    for wikipage in page['globalusage']:
        if word_filter.blacklisted(wikipage['title'].lower()):
            log_discarded(url, 'page usage "{0}"'.format(wikipage['title']))
            return None
        for blacklisted_category in category_blacklist:
            if blacklisted_category in wikipage['title']:  # substring matching
                log_discarded(url, 'page usage "{0}"'.format(wikipage['title']))
                return None
    return imageinfo


class CVAPIClient(object):
    "Microsoft Cognitive Services Client"
    def __init__(self, apikey):
        self.apikey = apikey

    def describe_picture(self, url):
        "Get description for a picture using Microsoft Cognitive Services"
        params = {'visualFeatures': 'Description,Adult'}
        json = {'url': url}
        headers = {'Content-Type': 'application/json',
                   'Ocp-Apim-Subscription-Key': self.apikey}

        result = None
        retries = 0

        while retries < 15 and not result:
            response = requests.post(CVAPI, json=json, params=params,
                                     headers=headers)
            if response.status_code == 429:
                log.error("Error from mscognitive: %s" % (response.json()))
                if retries < 15:
                    time.sleep(2)
                    retries += 1
                else:
                    log.error('failed after retrying!')

            elif response.status_code == 200 or response.status_code == 201:
                result = response.json() if response.content else None
            else:
                log.error("Error code: %d" % (response.status_code))
                log.error("url: %s" % url)
                try:
                    log.error(response.json())
                except:
                    log.error(response.text)
                retries += 1
                sleep = 20 + retries*4
                log.info("attempt: {0}, sleeping for {1}".format(retries, sleep))
                time.sleep(sleep)

        return result

    def get_picture_and_description(self, filename=None, max_retries=20):
        "Get a picture and a description. Retries until a usable result is produced or max_retries is reached."
        pic = None
        retries = 0
        while retries <= max_retries:  # retry max 20 times, until we get something good
            while pic is None:
                pic = get_picture(filename)
                if pic is None:
                    # We got a bad picture, let's wait a bit to be polite to the API server
                    time.sleep(1)
            url = pic['url']
            # Use a scaled-down image if the original is too big
            if pic['size'] > 3000000 or pic['width'] > 8192 or pic['height'] > 8192:
                url = pic['thumburl']

            result = self.describe_picture(url)

            if result is not None:
                description = result['description']
                adult = result['adult']
                if not adult['isAdultContent'] and not adult['isRacyContent']:  # no nudity and such
                    if len(description['captions']) > 0:
                        caption = description['captions'][0]['text']
                        caption = gender_neutralize(caption)
                        if not is_blacklisted(caption):
                            if not tag_blacklisted(description['tags']):
                                return Result(caption,
                                              description['tags'], url,
                                              pic['descriptionshorturl'])
                            else:
                                log_discarded(url, "tag blacklist", caption)
                                log.warning('tags: %s' % description['tags'])
                        else:
                            log_discarded(url, "caption blacklist", caption)
                    else:
                        log.warning("No caption for url: {0}".format(url))
                else:
                    log_discarded(url, "adult content", description['captions'])
            retries += 1
            log.warning("Not good, retrying...")
            pic = None
            time.sleep(3)  # sleep to be polite to the API servers

        raise Exception("Maximum retries exceeded, no good picture")


class NonClosingBytesIO(BytesIO):
    """" Like BytesIO, but doesn't close so easily.
    To prevent tweepy from closing the picture on error, this class requires
    to be specifically closed by adding a boolean parameter to the close() method.
    """

    def close(self, really=False):
        """ Close the BytesIO object, but only if you're really sure """
        if really:
            return super().close()


class Result(object):
    "Represents a picture and its description"
    def __init__(self, caption, tags, url, source_url):
        self.caption = caption
        self.tags = tags
        self.url = url
        self.source_url = source_url

    def download_picture(self):
        "Returns a BytesIO object for an image URL"
        retries = 0
        picture = None
        log.info("downloading " + self.url)
        while retries <= 20:
            if retries > 0:
                log.info('Trying again...')

            try:
                response = requests.get(self.url, headers=HEADERS)
            except requests.exceptions.RequestException as e:
                log.exception(e)
                response = None

            if response is not None and response.status_code == 200:
                picture = NonClosingBytesIO(response.content)
                return picture
            else:
                log.error("Fetching picture failed: " + response.status_code)
                retries += 1
                time.sleep(3)
        log.error("Maximum retries exceeded when downloading a picture")
        raise Exception("Maximum retries exceeded when downloading a picture")
