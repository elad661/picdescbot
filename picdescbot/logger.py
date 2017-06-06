# coding=utf-8
# picdescbot: a tiny twitter/tumblr bot that tweets random pictures from wikipedia and their descriptions
# this file contains logging related functionality
# Copyright (C) 2017 Elad Alfassa <elad@fedoraproject.org>
import logging
setup_done = False

fomatstr = '%(asctime)s : %(name)s: %(levelname)s: %(message)s'
datefmt = "%Y-%m-%d %H:%M:%S"

logging.basicConfig(level=logging.INFO,
                    format=fomatstr,
                    datefmt=datefmt,
                    filename="all.log")

formatter = logging.Formatter(fomatstr, datefmt=datefmt)

console = logging.StreamHandler()
console.setLevel(logging.INFO)
console.setFormatter(formatter)
logging.getLogger('').addHandler(console)

filtered = logging.FileHandler("filtered.log")
filtered.setLevel(logging.WARNING)
filtered.setFormatter(formatter)
logging.getLogger('').addHandler(filtered)


def get(name):
    return logging.getLogger(name)
