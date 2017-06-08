from __future__ import with_statement

import glob
import math
import os
import shutil
import time
from exceptions import RuntimeError
from functools import partial

import yaml
from flask import (Blueprint, flash, redirect, render_template, request,
                   send_from_directory, url_for)
from werkzeug import secure_filename

import cmath
from opsoro.console_msg import *
from opsoro.expression import Expression
from opsoro.hardware import Hardware
from opsoro.robot import Robot
from opsoro.sound import Sound
from opsoro.sound.tts import TTS

from opsoro.stoppable_thread import StoppableThread

from opsoro.users import Users

try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader


import tweepy
import re

def constrain(n, minn, maxn): return max(min(maxn, n), minn)


# from opsoro.expression import Expression

config = {
    'full_name':            'Sociono',
    'icon':                 'fa-info',
    'color':                'green',
    'difficulty':           4,
    'tags':                 [''],
    'allowed_background':   False,
    'multi_user':           True,
    'connection':           Robot.Connection.OFFLINE,
    'activation':           Robot.Activation.AUTO
}
config['formatted_name'] = config['full_name'].lower().replace(' ', '_')


get_path = partial(os.path.join, os.path.abspath(os.path.dirname(__file__)))

dof_positions = {}


def send_action(action):
    Users.send_app_data(config['formatted_name'], action, {})

def send_data(action, data):
    #def send_app_data(self, appname, action, data={}): from Opsoro.Users
    Users.send_app_data(config['formatted_name'], action, data)

def wait_for_sound():
    Sound.wait_for_sound()


sociono_t = None


def setup_pages(opsoroapp):
    sociono_bp = Blueprint(config['formatted_name'], __name__, template_folder='templates', static_folder='static')

    @sociono_bp.route('/', methods=['GET'])
    @opsoroapp.app_view
    def index():
        data = {'actions': {}, 'emotions': [], 'sounds': []}

        action = request.args.get('action', None)
        if action != None:
            data['actions'][action] = request.args.get('param', None)

        data['emotions'] = Expression.expressions

        filenames = glob.glob(get_path('../../data/sounds/*.wav'))

        for filename in filenames:
            data['sounds'].append(os.path.split(filename)[1])
        data['sounds'].sort()


        return opsoroapp.render_template(config['formatted_name'] + '.html', **data)

    @sociono_bp.route('/', methods=['POST'])
    @opsoroapp.app_view
    def post():

        data = {'actions': {}, 'emotions': [], 'sounds': []} # Overbodig ...

        # Auguste code --- Te verbeteren a.d.h.v. post actions
        
        if request.form['action'] == 'startTweepy':
            stopTwitter()
            if request.form['data']:
                social_id = []
                social_id.append(request.form['data'])
                startTwitter(social_id)

        if request.form['action'] == 'stopTweepy':
            stopTwitter()

        if request.form['action'] == 'autoLoopTweepyNext':
            stopTwitter()
            wait_for_sound()
            send_action(request.form['action'])
        if request.form['action'] == 'autoLoopTweepyStop':
            send_action(request.form['action'])

        if(request.form['action'] == 'playTweet'):
            playTweetInLanguage(request.form['text'], request.form['lang'])


        return opsoroapp.render_template(config['formatted_name'] + '.html', **data)


    opsoroapp.register_app_blueprint(sociono_bp)


access_token = '735437381696905216-BboISY7Qcqd1noMDY61zN75CdGT0OSc'
access_token_secret = 'd3A8D1ttrCxYV76pBOB389YqoLB32LiE0RVyoFwuMKUMb'
consumer_key = 'AcdgqgujzF06JF6zWrfwFeUfF'
consumer_secret = 'ss0wVcBTFAT6nR6hXrqyyOcFOhpa2sNW4cIap9JOoepcch93ky'

auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
auth.set_access_token(access_token, access_token_secret)

#getting new tweet
class MyStreamListener(tweepy.StreamListener):

    def on_status(self, status):
        dataToSend = processJson(status)
        print_info(dataToSend)
        if dataToSend['text']['filtered'] != None:
            send_data('dataFromTweepy', dataToSend)

api = tweepy.API(auth)
myStreamListener = MyStreamListener()
myStream = tweepy.Stream(auth=api.auth, listener=myStreamListener)


# Default functions for setting up, starting and stopping an app
def setup(opsoroapp):
    pass

def start(opsoroapp):
    pass

def stop(opsoroapp):
    stopTwitter()


def startTwitter(twitterWords):
    global myStream
    myStream.filter(track=twitterWords, async=True)


    print_info(twitterWords)

def stopTwitter():
    global myStream
    myStream.disconnect()

    print_info("stop twitter stream")


# Thibaud code

#process tweepy json
def processJson(status):
    data = { 
        "user": { 
            "username": status._json["user"]["screen_name"], 
            "profile_picture": status._json["user"]["profile_image_url_https"]
        }, 
        "text": { 
            "original": status.text, 
            "filtered": filterTweet(status),
            "lang": status.lang
        }
    }

    return data

def filterTweet(status):
    #alles in nieuw object aanmaken en steken
    encodedstattext = status.text.encode('utf-8')
    strTweet = str(encodedstattext)
    strTweet = strTweet.replace("RT","Retweet", 1)
    strTweet = strTweet.decode('unicode_escape').encode('ascii','ignore')
    strTweet = re.sub(r'\w+:\/{2}[\d\w-]+(\.[\d\w-]+)*(?:(?:\/[^\s/]*))*', '', strTweet, flags=re.MULTILINE) # re -> import re (regular expression)
    strTweet = languageCheck(strTweet, status)
    return strTweet

def languageCheck(strTweet,status):
    if status.lang == "en":
        return strTweet.replace("@","from ", 1)
    elif status.lang == "nl":
        return strTweet.replace("@","van ", 1)
    elif status.lang == "de":
        return strTweet.replace("@","von ", 1)
    elif status.lang == "fr":
        return strTweet.replace("@","de ", 1)

def sayTweetInLanguage(status):
    file_path = str(os.path.expanduser('~/sociono'))
    TTS.create_espeak(status.text, file_path, status.lang, "m", 10, 100)

def playTweetInLanguage(text, lang):

    if not os.path.exists("/tmp/OpsoroTTS/"):
        os.makedirs("/tmp/OpsoroTTS/")

    full_path = os.path.join(
        get_path("/tmp/OpsoroTTS/"), "Tweet.wav")

    if os.path.isfile(full_path):
        os.remove(full_path)

    TTS.create_espeak(text, full_path, lang, "f", "5", "150")

    Sound.play_file(full_path)
