# Copyright (C) 2016   CzT/Vladislav Ivanov
import json
import logging
import os
import random
import re
import string
import threading
import time
from collections import OrderedDict

import requests
from ws4py.client.threadedclient import WebSocketClient

from modules.gui import MODULE_KEY
from modules.helper.message import TextMessage, SystemMessage, Emote
from modules.helper.module import ChatModule
from modules.helper.system import translate_key, EMOTE_FORMAT

logging.getLogger('requests').setLevel(logging.ERROR)
log = logging.getLogger('sc2tv')
SOURCE = 'fs'
SOURCE_ICON = 'http://funstream.tv/build/images/icon_home.png'
FILE_ICON = os.path.join('img', 'fs.png')
SYSTEM_USER = 'Peka2.tv'
SMILE_REGEXP = r':(\w+|\d+):'
SMILE_FORMAT = ':{}:'
API_URL = 'http://funstream.tv/api{}'

PING_DELAY = 10

CONF_DICT = OrderedDict()
CONF_DICT['gui_information'] = {'category': 'chat'}
CONF_DICT['config'] = OrderedDict()
CONF_DICT['config']['show_pm'] = True
CONF_DICT['config']['socket'] = 'ws://funstream.tv/socket.io/'
CONF_DICT['config']['show_channel_names'] = True
CONF_DICT['config']['channels_list'] = []

CONF_GUI = {
    'config': {
        'hidden': ['socket'],
        'channels_list': {
            'view': 'list',
            'addable': 'true'
        },
    },
    'non_dynamic': ['config.socket'],
    'icon': FILE_ICON}


class Peka2TVAPIError(Exception):
    pass


def get_channel_name(channel_name):
    payload = {
        'slug': channel_name
    }
    channel_req = requests.post(API_URL.format('/stream'), timeout=5, data=payload)
    if channel_req.ok:
        return channel_req.json()['owner']['name']
    raise Peka2TVAPIError("Unable to get channel name")


def allow_smile(smile, subscriptions, allow=False):
    if smile['user']:
        channel_id = smile['user']['id']
        for sub in subscriptions:
            if sub == channel_id:
                allow = True
    else:
        allow = True
    return allow


class FsChatMessage(TextMessage):
    def __init__(self, user, text, subscr):
        self._user = user
        self._text = text
        self._subscriptions = subscr

        TextMessage.__init__(self, source=SOURCE, source_icon=SOURCE_ICON,
                             user=self.user, text=self.text)

    def process_smiles(self, smiles):
        smiles_array = re.findall(SMILE_REGEXP, self._text)
        for smile in smiles_array:
            for smile_find in smiles:
                if smile_find['code'] == smile.lower():
                    if allow_smile(smile_find, self._subscriptions):
                        self._text = self._text.replace(SMILE_FORMAT.format(smile),
                                                        EMOTE_FORMAT.format(smile))
                        self._emotes.append(Emote(smile, smile_find['url']))

    def process_pm(self, to_name, channel_name, show_pm):
        self.text = u'@{},{}'.format(to_name, self.text)
        if to_name == channel_name:
            if show_pm:
                self._pm = True


class FsSystemMessage(SystemMessage):
    def __init__(self, text, emotes=None, category='system'):
        if emotes is None:
            emotes = []
        SystemMessage.__init__(self, text, source=SOURCE, source_icon=SOURCE_ICON,
                               user=SYSTEM_USER, emotes=emotes, category=category)


class FsChat(WebSocketClient):
    def __init__(self, ws, queue, channel_name, **kwargs):
        super(self.__class__, self).__init__(ws, protocols=kwargs.get('protocols', None))
        # Received value setting.
        self.source = SOURCE
        self.queue = queue
        self.channel_name = channel_name
        self.glob = kwargs.get('glob')
        self.main_thread = kwargs.get('main_thread')  # type: FsThread
        self.chat_module = kwargs.get('chat_module')  # type: sc2tv
        self.crit_error = False

        self.channel_id = self.fs_get_id()

        self.smiles = kwargs.get('smiles')

        self.iter = 0
        self.duplicates = []
        self.users = []
        self.request_array = []
        self.bufferForDup = 20

    def opened(self):
        log.info("Websocket Connection Succesfull")
        self.fs_system_message(translate_key(MODULE_KEY.join(['sc2tv', 'connection_success'])), category='connection')

    def closed(self, code, reason=None):
        """
        Codes used by LC
        4000 - Normal disconnect by LC
        4001 - Invalid Channel ID

        :param code: 
        :param reason: 
        """
        self.chat_module.set_offline(self.glob)
        if code in [4000, 4001]:
            self.crit_error = True
            self.fs_system_message(translate_key(
                MODULE_KEY.join(['sc2tv', 'connection_closed'])).format(self.glob),
                                category='connection')
        else:
            log.info("Websocket Connection Closed Down")
            self.fs_system_message(
                translate_key(MODULE_KEY.join(['sc2tv', 'connection_died'])).format(self.glob),
                category='connection')
            timer = threading.Timer(5.0, self.main_thread.connect)
            timer.start()

    def fs_system_message(self, message, category='system'):
        self.queue.put(FsSystemMessage(message, category=category))

    def received_message(self, mes):
        if mes.data == '40':
            return
        if mes.data in ['2', '3']:
            return
        regex = re.match('(\d+)(.*)', mes.data)
        sio_iter, json_message = regex.groups()
        if sio_iter == '0':
            self._process_welcome()
        elif sio_iter[:2] in '42':
            self._process_websocket_event(json.loads(json_message))
        elif sio_iter[:2] in '43':
            self._process_websocket_ack(sio_iter[2:], json.loads(json_message))

    def fs_get_id(self):
        # We get ID from POST request to funstream API, and it hopefuly
        #  answers us the correct ID of the channel we need to connect to
        payload = {
            'id': None,
            'name': self.channel_name
        }
        try:
            request = requests.post(API_URL.format("/user"), data=payload, timeout=5)
            if request.status_code == 200:
                channel_id = json.loads(re.findall('{.*}', request.text)[0])['id']
                return channel_id
            else:
                error_message = request.json()
                if 'message' in error_message:
                    log.error("Unable to get channel ID. {0}".format(error_message['message']))
                    self.closed(1000, 'INV_CH_ID')
                else:
                    log.error("Unable to get channel ID. No message available")
                    self.closed(1000, 'INV_CH_ID')
        except requests.ConnectionError:
            log.info("Unable to get information from api")
        return None

    def fs_join(self):
        # Then we send the message acording to needed format and
        #  hope it joins us
        if self.channel_id:
            payload = [
                '/chat/join',
                {
                    'channel': 'stream/{0}'.format(str(self.channel_id))
                }
            ]
            self.fs_send(payload)

            msg_joining = translate_key(MODULE_KEY.join(['sc2tv', 'joining']))
            self.fs_system_message(msg_joining.format(self.glob), category='connection')
            log.info(msg_joining.format(self.channel_id))

    def fs_send(self, payload):
        iter_sio = "42"+str(self.iter)

        self.send('{iter}{payload}'.format(iter=iter_sio,
                                           payload=json.dumps(payload)))
        history_item = {
            'iter': str(self.iter),
            'payload': payload
        }
        self.iter += 1
        if len(self.request_array) > 20:
            del self.request_array[0]
        self.request_array.append(history_item)

    def fs_ping(self):
        ping_thread = FsPingThread(self)
        ping_thread.start()

    def _process_websocket_event(self, message):
        event_from, event_dict = message
        if event_from == '/chat/message':
            self._process_message(event_dict)

    def _process_websocket_ack(self, sio_id, message):
        if isinstance(message, list):
            if len(message) == 1:
                message = message[0]
        for item in self.request_array:  # type: dict
            if item['iter'] == sio_id:
                item_path = item['payload'][0]
                self._process_answer(item_path, message)
                break

    def _process_welcome(self):
        self.fs_join()
        self.fs_ping()

    def _process_answer(self, path, message):
        if path == '/chat/join':
            self._process_joined()
        elif path == '/chat/channel/list':
            self._process_channel_list(message)

    def _process_message(self, message):
        try:
            self.duplicates.index(message['id'])
        except ValueError:
            msg = FsChatMessage(message['from']['name'], message['text'], message['store']['subscriptions'])
            msg.process_smiles(self.smiles)
            if message['to']:
                msg.process_pm(message['to'].get('name'), self.channel_name,
                               self.chat_module.conf_params()['config']['config'].get('show_pm'))

            self.duplicates.append(message['id'])
            if len(self.duplicates) > self.bufferForDup:
                self.duplicates.pop(0)
            self._send_message(msg)

    def _process_joined(self):
        self.chat_module.set_online(self.glob)
        self.fs_system_message(
            translate_key(MODULE_KEY.join(['sc2tv', 'join_success'])).format(self.glob), category='connection')

    def _process_channel_list(self, message):
        self.chat_module.set_viewers(self.glob, message['result']['amount'])

    def _post_process_multiple_channels(self, message):
        if self.chat_module.conf_params()['config']['config']['show_channel_names']:
            message.channel_name = self.glob

    def _send_message(self, comp):
        self._post_process_multiple_channels(comp)
        self.queue.put(comp)


class FsPingThread(threading.Thread):
    def __init__(self, ws):
        threading.Thread.__init__(self)
        self.daemon = "True"
        # Using main websocket
        self.ws = ws  # type: FsChat

    def run(self):
        while not self.ws.terminated:
            self.ws.send("2")
            self.ws.chat_module.get_viewers(self.ws)
            time.sleep(PING_DELAY)


class FsThread(threading.Thread):
    def __init__(self, queue, socket, channel_name, **kwargs):
        threading.Thread.__init__(self)
        # Basic value setting.
        # Daemon is needed so when main programm exits
        # all threads will exit too.
        self.daemon = "True"
        self.queue = queue
        self.socket = socket
        self.channel_name = get_channel_name(channel_name)
        self.glob = channel_name
        self.chat_module = kwargs.get('chat_module')
        self.smiles = []
        self.ws = None
        self.kwargs = kwargs

    def run(self):
        self.connect()

    def connect(self):
        # Connecting to funstream websocket
        try_count = 0
        while True:
            try_count += 1
            log.info("Connecting, try {0}".format(try_count))
            self._get_info()
            self.ws = FsChat(self.socket, self.queue, self.channel_name, glob=self.glob,
                             protocols=['websocket'], smiles=self.smiles,
                             main_thread=self, **self.kwargs)
            if self.ws.crit_error:
                log.critical("Got critical error, halting")
                break
            elif self.ws.channel_id and self.smiles:
                self.ws.connect()
                self.ws.run_forever()
                break
            time.sleep(5)

    def stop(self):
        self.ws.send("11")
        self.ws.close(4000, reason="CLOSE_OK")

    def _get_info(self):
        if not self.smiles:
            try:
                smiles = requests.post(API_URL.format('/smile'), timeout=5)
                if smiles.status_code == 200:
                    smiles_answer = smiles.json()
                    for smile in smiles_answer:
                        self.smiles.append(smile)
            except requests.ConnectionError:
                log.error("Unable to get smiles")


class Sc2tvMessage(object):
    def __init__(self, nickname, text):
        message = [
            u'/chat/message',
            {
                u'from': {
                    u'color': 0,
                    u'name': u'{}'.format(nickname)},
                u'text': u'{}'.format(text),
                u'to': None,
                u'store': {u'bonuses': [], u'icon': 0, u'subscriptions': []},
                u'id': ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(10))
            }
        ]
        self.data = '42{}'.format(json.dumps(message))


class TestSc2tv(threading.Thread):
    def __init__(self, main_class):
        super(TestSc2tv, self).__init__()
        self.main_class = main_class  # type: sc2tv
        self.main_class.rest_add('POST', 'push_message', self.send_message)
        self.fs_thread = None

    def run(self):
        while True:
            try:
                thread = self.main_class.channels.items()[0][1]
                if thread.ws:
                    self.fs_thread = thread.ws
                    break
            except:
                continue
        log.info("sc2tv Testing mode online")

    def send_message(self, *args, **kwargs):
        nickname = kwargs.get('nickname', 'super_tester')
        text = kwargs.get('text', 'Kappa 123')

        self.fs_thread.received_message(Sc2tvMessage(nickname, text))


class sc2tv(ChatModule):
    def __init__(self, *args, **kwargs):
        log.info("Initializing funstream chat")
        ChatModule.__init__(self, *args, **kwargs)

        self.socket = CONF_DICT['config']['socket']

    def _conf_settings(self, *args, **kwargs):
        return CONF_DICT

    def _gui_settings(self, *args, **kwargs):
        return CONF_GUI

    def _test_class(self):
        return TestSc2tv(self)

    def get_viewers(self, ws):
        user_data = {'name': ws.channel_name}
        status_data = {'slug': ws.channel_name}
        request = ['/chat/channel/list', {'channel': 'stream/{0}'.format(str(ws.channel_id))}]

        try:
            user_request = requests.post(API_URL.format('/user'), timeout=5, data=user_data)
            if user_request.status_code == 200:
                status_data['slug'] = user_request.json()['slug']
        except requests.ConnectionError:
            log.error("Unable to get smiles")

        try:
            status_request = requests.post(API_URL.format('/stream'), timeout=5, data=status_data)
            if status_request.status_code == 200:
                if status_request.json()['online']:
                    self.set_online(ws.channel_name)
                    ws.fs_send(request)
                else:
                    self.set_viewers(ws.channel_name, 'N/A')

        except requests.ConnectionError:
            log.error("Unable to get smiles")

    def _set_chat_online(self, chat):
        ChatModule.set_chat_online(self, chat)
        self.channels[chat] = FsThread(self.queue, self.socket, chat, chat_module=self)
        self.channels[chat].start()

    def apply_settings(self, **kwargs):
        ChatModule.apply_settings(self, **kwargs)
