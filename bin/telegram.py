#!/usr/bin/env python3
# -*-coding:UTF-8 -*

import json
import asyncio
import logging
import magic
import os
import re
import sys
import time
import base64

import subprocess

from datetime import datetime
from hashlib import sha256
from uuid import uuid4

# from libretranslatepy import LibreTranslateAPI

from telethon import TelegramClient, events
# from telethon import helpers
from telethon.utils import parse_username

from telethon.tl.functions.channels import JoinChannelRequest, LeaveChannelRequest, GetForumTopicsRequest, GetChannelRecommendationsRequest

from telethon.tl.types import Channel, User, ChannelParticipantsAdmins, PeerUser, PeerChat, PeerChannel, ForumTopicDeleted
from telethon.tl.types import InputPeerChat, InputPeerChannel, InputPeerUser
from telethon.tl.types import MessageEntityUrl, MessageEntityTextUrl, MessageEntityMention, MessageEntityMentionName, MessageService
from telethon.tl.types import ReactionEmoji, ReactionCustomEmoji, ReactionPaid
from telethon.tl.types import Chat, ChatFull, ChannelFull  # ChatEmpty
from telethon.tl.types import ChatInvite, ChatInviteAlready, ChatInvitePeek
from telethon.tl.functions.users import GetFullUserRequest  # https://tl.telethon.dev/constructors/users/user_full.html
from telethon.tl.functions.messages import GetFullChatRequest  # chat_id=-00000000
# https://tl.telethon.dev/methods/messages/get_full_chat.html
from telethon.tl.functions.channels import GetFullChannelRequest  # channel='username'
# https://tl.telethon.dev/methods/channels/get_full_channel.html
from telethon.tl.functions.messages import CheckChatInviteRequest, ImportChatInviteRequest
from telethon.tl.functions.contacts import SearchRequest
from telethon.tl.types.messages import ChatsSlice
from telethon.tl.functions.chatlists import CheckChatlistInviteRequest
from telethon.tl.types.chatlists import ChatlistInvite, ChatlistInviteAlready

# errors
from telethon.errors.rpcbaseerrors import BadRequestError
from telethon.errors.rpcerrorlist import ChatAdminRequiredError  # UserNotParticipantError
from telethon.errors.rpcerrorlist import InviteHashExpiredError, InviteHashInvalidError
from telethon.errors import ChannelsTooMuchError, ChannelInvalidError, ChannelPrivateError, InviteRequestSentError
from telethon.errors import ChannelPublicGroupNaError, UserCreatorError, UserNotParticipantError, InviteHashEmptyError
from telethon.errors import UsersTooMuchError, UserAlreadyParticipantError, SessionPasswordNeededError
from telethon.errors import QueryTooShortError, SearchQueryEmptyError, TimeoutError
from telethon.errors import UsernameInvalidError, FileIdInvalidError
# from telethon.errors.common import MultiError

# import logging
# logging.basicConfig(level=logging.DEBUG)

DISABLED_USERNAME = {"addemoji", "addlist", "addstickers", "addtheme", "boost", "confirmphone", "contact",
                     "giftcode", "invoice", "joinchat", "login", "proxy", "setlanguage", "share", "socks"} # + 'settings' + telegrampassport

RE_VALID_USERNAME = re.compile(r"^[a-z](?:(?!__)\w){3,30}[a-z\d]$")

DOWNLOAD_MIMETYPES = {'application': {'csv', 'json', 'pdf'}, 'text': {'csv', 'plain', 'html'}}

def _get_file_mimetype(content):
    return magic.from_buffer(content, mime=True)

def extract_file_metadata(file):
    process = subprocess.run(['exiftool', file], stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
    if process.returncode == 0:
        exif = {}
        for line in process.stdout.decode().split('\n'):
            if line:
                name, value = line.split(':', 1)
                exif[name.strip()] = value.strip()
        return exif
    else:
        print(process.stderr.decode())

def delete_file_metadata(file):
    process = subprocess.run(['exiftool', '-overwrite_original', '-all=', file], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if process.returncode == 0:
        print(process.stdout.decode())
    else:
        print(process.stderr.decode())
    process = subprocess.run(['qpdf', '--linearize', '--replace-input', file], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if process.returncode == 0:
        print(process.stdout.decode())
    else:
        print(process.stderr.decode())


def convert_pdf_to_pdfa(content):
    name = uuid4()
    pdf_file = f'/tmp/{name}.pdf'
    print(pdf_file)
    with open(pdf_file, 'wb') as f:
        f.write(content)

    file_metadata = extract_file_metadata(pdf_file)
    delete_file_metadata(pdf_file)

    process = subprocess.run(['gs', '-dQUIET', '-sstdout=/dev/null',
                              '-dBATCH', '-dNOPAUSE', '-dNOOUTERSAVE',
                              '-dCompatibilityLevel=1.4',
                              '-dEmbedAllFonts=true', '-dSubsetFonts=true',
                              '-dCompressFonts=true', '-dCompressPages=true',
                              '-sColorConversionStrategy=UseDeviceIndependentColor',
                              '-dDownsampleMonoImages=false', '-dDownsampleGrayImages=false', '-dDownsampleColorImages=false',
                              '-dAutoFilterColorImages=false', '-dAutoFilterGrayImages=false',
                              '-sDEVICE=pdfwrite',
                              f'-sOutputFile=/tmp/conv_{name}', pdf_file
                              ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if process.returncode == 0:
        print(process.stdout.decode())
    else:
        print(process.stderr.decode())

    process = subprocess.run(['gs', '-dQUIET', '-sstdout=/dev/null',
                              '-dPDFA=2', '-dBATCH', '-dNOPAUSE', '-dNOOUTERSAVE',
                              '-dCompatibilityLevel=1.4', '-dPDFACompatibilityPolicy=1',
                              '-sColorConversionStrategy=UseDeviceIndependentColor',
                              '-sDEVICE=pdfwrite',
                              f'-sOutputFile=/tmp/{name}_pdfa.pdf', f'/tmp/conv_{name}', 'PDFA_def.ps',
                              ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if process.returncode == 0:
        print(process.stdout.decode())
        with open(f'/tmp/{name}_pdfa.pdf', 'rb') as f:
            content = f.read()

        # cleanup
        os.remove(pdf_file)
        os.remove(f'/tmp/conv_{name}')
        os.remove(f'/tmp/{name}_pdfa.pdf')
        return content
    else:
        print(process.stderr.decode())


def is_valid_username(username):
    username = username.lower()
    if RE_VALID_USERNAME.match(username):
        if username not in DISABLED_USERNAME:
            return username, 'username'
    return None, None

def is_valid_join_hash(invite_hash):  # TODO ######################################
    return invite_hash, 'invite'

def _parse_entity(entity):
    entity = entity.lower()
    # Phone + Join
    if entity[0] == '+':
        # Phone
        if entity[1:].isdigit():
            return entity, 'phone'
        # Invite
        if is_valid_join_hash(entity[1:]):
            return entity, 'invite'
    # Username
    else:
        return is_valid_username(entity)

def parse_entity(text):
    if text.startswith('@'):
        return is_valid_username(text[1:])

    if text.startswith("tg://") or text.startswith("tg:"):
        if text.startswith("tg://"):
            text = text[5:]
        else:
            text = text[3:]
        text = text.split('?', 1)

        # tg://user?id=<id>
        if text[0] == "user":
            if text[1].startswith("id="):
                entity_id = text[1].split('&', 1)[0][3:]
                if entity_id.isdigit():
                    return int(entity_id), 'id'
        # tg://join?invite=<hash>
        # elif text[0] == "join":

        # tg://openmessage

        # tg://resolve?domain=<username> &thread= ...  + videochat + story + ???bot links???
        # + ? boost ?

        # tg://privatepost?channel=<channel_id>&post= ...

        # tg://resolve?phone=
        # tg://resolve?phone=<phone_number>

    else:
        if text.startswith("https://"):
            text = text[8:]
        elif text.startswith("http://"):
            text = text[7:]

        if 't.me' in text:  # TODO remove ? ???
            u = text.split('.')
            if u[1] == 't' and u[2] == 'me':
                username = u[0]
                return is_valid_username(username)

        text = text.replace("telegram.me", "t.me")
        text = text.replace("telegram.dog", "t.me")

        text = text.split('/')
        if text[0] == 't.me' and len(text) > 1:
            # t.me/c/chat_id
            if text[1] == 'c':  ### warning boost link: t.me/c/<id>?boost  # TODO remove ?
                entity_id = text[2]
                if entity_id.isdigit():
                    return int(entity_id), 'id'
            elif text[1] == 'joinchat':
                entity = text[2].split('?', 1)[0]
                return is_valid_join_hash(entity)
            # t.me/username
            else:
                entity = text[1].split('?', 1)[0]
                return _parse_entity(entity)
    return None, None


class TGFeeder:

    # dialog vs chats ???

    # ail_url ail_key ail_verifycert ail_feeder + disabled option
    def __init__(self, tg_api_id, tg_api_hash, session_name, ail_clients=None, extract_mentions=False): # TODO create downloads dir
        self.logger = logging.getLogger()  # TODO FORMAT LOGS

        self.source = 'ail_feeder_telegram'
        self.source_uuid = '9cde0855-248b-4439-b964-0495b9b2b8db'

        self.extract_mentions = extract_mentions

        self.tg_api_id = int(tg_api_id)
        self.tg_api_hash = tg_api_hash
        self.session_name = session_name

        self.client = self.get_client()
        self.loop = self.client.loop

        if ail_clients:
            self.ails = ail_clients
        else:
            self.ails = None

        # self.lt = LibreTranslateAPI("http://localhost:5000")

        self.subchannels = {}

        self.map_username_invite_id = {}
        self.chats = {}
        self.users = {}  # TODO ADD ID USER IF DOWNLOADED IMAGE
        self.invalid_id = set()
        # TODO END CLEANUP

    def send_to_ail(self, data, meta, data_sha256=None):
        for ail in self.ails:
            ail.feed_json_item(data, meta, self.source, self.source_uuid, data_sha256=data_sha256)

    def update_chats_cache(self, meta_chats):
        chat_id = meta_chats['id']
        if chat_id not in self.chats:
            self.chats[chat_id] = meta_chats

    def _get_default_dict(self):
        return {'meta': {}, 'source': self.source, 'source-uuid': self.source_uuid}

    def get_client(self):
        return TelegramClient(self.session_name, self.tg_api_id, self.tg_api_hash)

    def is_connected(self):
        return self.client.is_connected()

    def connect(self):
        self.client.start()
        if not self.client.is_connected():
            self.logger.warning('Connection error')

    # def translate(self, text):
    #     # get text language
    #     translation = ''
    #     lang = lt.detect(text)[0]
    #     if lang['confidence'] >= 50:
    #         translation = lt.translate(text, source=lang['language'], target='en')
    #     return translation

    async def get_chats(self, meta=True):
        channels = []
        async for dialog_obj in self.client.iter_dialogs():
            # remove self chats
            # if not dialog_obj.is_user:
            channel_id = dialog_obj.id
                # negative: is a group, positive: single person # TODO check chat id padding
            if meta:
                channels.append(self._unpack_get_chat(dialog_obj.entity))
            else:
                channels.append(channel_id)
        return channels

    def _unpack_invite(self, invite):
        meta = {}
        if isinstance(invite, ChatInvite):
            meta['name'] = invite.title
            # meta['photo'] = invite.photo
            meta['participants'] = invite.participants_count
            # flags: channel, broadcast, public, megagroup, request_needed
            if invite.about:
                meta['about'] = invite.about  # TODO what is about ???
            if invite.participants:
                users = []
                for user in invite.participants:
                    users.append(self._unpack_user(user))
                meta['users'] = users
        elif isinstance(invite, ChatInviteAlready):
            return self._unpack_get_chat(invite.chat)
        elif isinstance(invite, ChatInvitePeek):
            meta = self._unpack_get_chat(invite.chat)
            meta['expire'] = unpack_datetime(invite.expires)
        return meta

    # TODO validate/sanitize invite hash
    async def check_invite(self, invite):
        try:
            invite = await self.client(CheckChatInviteRequest(invite))
            # print(invite)
            return self._unpack_invite(invite)
        except InviteHashExpiredError:
            self.logger.warning('Error: The chat the user tried to join has expired and is not valid anymore')
        except InviteHashInvalidError:
            self.logger.warning('Error: The invite hash is invalid')

    async def join_chat_discussion(self, chat):
        chat_full = await self.get_chat_full(chat, image=False)
        if chat_full['discussion']['channel'] == chat_full['id']:
            meta_discussion = await self.join_chat(chat=chat_full['discussion']['chat'], discussion=False)
            return meta_discussion

    async def join_chat(self, chat=None, invite=None, discussion=True):
        # join a public chat/channel
        # channel are a special form of chat
        if chat:
            try:
                chat = int(chat)
            except (TypeError, ValueError):
                pass
            chat = await self.client.get_entity(chat)  # TODO
            try:
                updates = await self.client(JoinChannelRequest(chat))
                meta = {}
                if updates:
                    if updates.chats:
                        chat = updates.chats[0]
                        meta = self._unpack_get_chat(chat)
                        if chat.has_link and discussion:
                            meta_discussion = await self.join_chat_discussion(chat)
                            if meta_discussion:
                                return [meta, meta_discussion]
                return meta

            except ChannelsTooMuchError:
                self.logger.error('You have joined too many channels/supergroups')
            except ChannelInvalidError:
                self.logger.error(f'Invalid channel id/name: {chat}')
            except ChannelPrivateError:
                self.logger.error(f'This channel is private or this account was banned: {chat}')
            except InviteRequestSentError:
                self.logger.warning(f'Invite Request Sent. You have successfully requested to join this chat or channel {chat}')
        # join a private chat or channel
        if invite:
            # TODO validate_join_code option -> check if hash
            try:
                updates = await self.client(ImportChatInviteRequest(invite))
                meta = {}
                if updates:
                    if updates.chats:
                        chat = updates.chats[0]
                        meta = self._unpack_get_chat(updates.chats[0])
                        if chat.has_link and discussion:
                            meta_discussion = await self.join_chat_discussion(chat)
                            if meta_discussion:
                                return [meta, meta_discussion]
                return meta

            except ChannelsTooMuchError:
                self.logger.error('You have joined too many channels/supergroups')
            except InviteHashEmptyError:
                self.logger.error('The invite hash is empty.')
            except InviteHashExpiredError:
                self.logger.error(f'The chat you tried to join has expired and is not valid anymore: {invite}')
            except InviteHashInvalidError:
                self.logger.error(f'The invite hash is invalid: {invite}')
            except InviteRequestSentError:
                self.logger.warning(f'You have successfully requested to join this chat or channel: {invite}')
            except SessionPasswordNeededError:
                self.logger.error('Two-steps verification is enabled and a password is required.')
            except UsersTooMuchError:
                self.logger.error('The maximum number of users for this chat has been exceeded')
            except UserAlreadyParticipantError:
                self.logger.error('you are already a participant of this chat')

    async def leave_chat(self, chat):  # delete_dialog ???
        # chat = await self.client.get_entity(chat)
        try:
            updates = await self.client(LeaveChannelRequest(chat))
            # print(updates)
            if updates:
                meta = {}
                if updates.chats:
                    meta = self._unpack_get_chat(updates.chats[0])
                return meta
        except ChannelInvalidError:
            self.logger.error(f'Invalid channel id/name: {chat}')
        except ChannelPrivateError:
            self.logger.error(f'This channel is private or this account was banned: {chat}')
        except ChannelPublicGroupNaError:
            self.logger.error(f'channel/supergroup not available: {chat}')
        except UserCreatorError:
            self.logger.error(f'You can\'t leave this channel, because you\'re its creator.: {chat}')
        except UserNotParticipantError:
            self.logger.warning(f'You are not a member of this channel: {chat}')

    async def get_user_meta(self, user=None):
        if user.id not in self.users and not isinstance(user, Chat):
            self.users[user.id] = await self.get_user(user)
        meta = self.users[user.id]
        return meta

    async def get_user(self, user):
        # return {}
        try:
            full = await self.client(GetFullUserRequest(id=user))
            # print(full)
            user_f = full.full_user
            # birthday
            # personal_channel_id
            # ttl_period
            # print(user_f.birthday)
            # print(user_f.personal_channel_id)
            # print(user_f.ttl_period)
            meta = self._unpack_user(user)
            if user_f.about:
                meta['info'] = user_f.about
            # common_chats_count
            if user_f.profile_photo:
                try:
                    icon = await asyncio.wait_for(self.client.download_profile_photo(user, file=bytes), 30)
                except asyncio.exceptions.TimeoutError:
                    print('TIMEOUT')
                    try:
                        icon = await asyncio.wait_for(self.client.download_profile_photo(user, file=bytes), 30)
                    except asyncio.exceptions.TimeoutError:
                        icon = None
                        print('TIMEOUT Small photo')
                except FileIdInvalidError:
                    print('ERROR: FileIdInvalidError')
                    icon = None

                if icon:
                    meta['icon'] = base64.standard_b64encode(icon).decode()

            # print(user.profile_photo)
            return meta
        except ValueError as e:
            print(e)
            return {}

    async def get_entity_id(self, entity):
        try:
            entity = await self.client.get_input_entity(entity)
        except ValueError:
            self.logger.error(f'Could not find the entity {entity}')
            return None
        except UsernameInvalidError:
            self.logger.error(f'Could not find the username {entity}')
            return None
        if entity:
            if isinstance(entity, InputPeerChat):
                return entity.chat_id
            elif isinstance(entity, InputPeerChannel):
                return entity.channel_id
            elif isinstance(entity, InputPeerUser):
                return entity.user_id

    # Note: entity ID: only work if is in a dialog or in the same chat, client.get_participants(group) need to be called
    #       -
    async def get_entity(self, entity, entity_id=None, r_id=False, r_obj=False, similar=False, full=False, load_dialog=True):  # TODO load_dialog global
        if load_dialog:
            await self.client.get_dialogs()
        if entity_id:
            try:
                entity = int(entity_id)
            except (TypeError, ValueError):
                pass
        try:
            entity = int(entity)
        except (TypeError, ValueError):
            pass
        try:
            r_ob = await self.client.get_entity(entity)
            # print(r_ob)
            if r_obj:
                return r_ob

            if full:
                entity = await self.get_chat_full(r_ob, image=False)
            else:
                entity = self._unpack_get_chat(r_ob)

            if similar:
                if not isinstance(r_ob, User):
                    recommendations = await self.get_chat_recommendations(r_ob)
                    if recommendations:
                        entity['similar'] = recommendations
            if r_id:
                return entity['id']
            else:
                return entity
        except ValueError:
            self.logger.error(f'Could not find the entity {entity}')
        except ChannelPrivateError:
            self.logger.error(f'This channel is private or this account was banned: {entity}')
        except InviteHashExpiredError:
            self.logger.error(f'This invitation is expired: {entity}')
        except UsernameInvalidError: # TODO CACHE IT
            self.logger.error(f'Could not find the username {entity}')

    async def get_entity_meta(self, entity, entity_type='id'):
        if entity_type == 'id':
            if not entity:
                return None
            entity_id = entity
            entity = None
        else:
            entity_id = entity.id
            entity = entity

        if entity_id in self.chats:
            return self.chats[entity_id]
        elif entity_id in self.users:
            return self.users[entity_id]
        elif entity_id in self.invalid_id:
            return None
        else:
            if not entity:
                time.sleep(1)
                entity = await self.get_entity(None, entity_id=entity_id, r_obj=True, load_dialog=False)
                time.sleep(3)
            if entity:
                if isinstance(entity, Chat) or isinstance(entity, Channel):
                    return await self.get_chat_meta(chat=entity)
                elif isinstance(entity, User):
                    return await self.get_user_meta(user=entity)
            self.invalid_id.add(entity_id)
            return None

    async def get_entity_meta_from_text(self, text):
        entity, e_type = parse_entity(text)
        print(text)
        print(entity, e_type)
        if e_type and entity:
            if e_type == 'id':
                return await self.get_entity_meta(entity)
            elif e_type == 'invite' or e_type == 'username':
                if entity in self.map_username_invite_id:
                    return await self.get_entity_meta(self.map_username_invite_id[entity])
                else:
                    if e_type == 'invite':
                        if entity.startswith('+'):
                            text_entity = f't.me/{entity}'
                        else:
                            text_entity = f't.me/+{entity}'  # TODO TESSSSSSSSSSSSSTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTT
                    else:
                        text_entity = entity
                    ent = await self.get_entity(text_entity, r_obj=True, load_dialog=False)
                    time.sleep(1)
                    if ent:
                        self.map_username_invite_id[entity] = ent.id
                        print(ent)
                        return await self.get_entity_meta(ent, entity_type='entity')
                    else:
                        self.map_username_invite_id[entity] = None
                        return None
        return None

    async def get_chat_users(self, chat, admin=False):
        users = []
        if admin:
            user_filter = ChannelParticipantsAdmins
        else:
            user_filter = None
        chat = await self.get_entity(chat, r_id=True)
        try:
            async for user in self.client.iter_participants(chat, filter=user_filter):
                user_meta = self._unpack_user(user)
                users.append(user_meta)
        except ChatAdminRequiredError:
            self.logger.error(f'{chat}: Chat admin privileges required')
            sys.exit(0)
        # except MultiError as e:
        #     if isinstance(e.exceptions[0], ChatAdminRequiredError):
        #         self.logger.error(f'Error, {chat}: Chat admin privileges required')
        #     else:
        #         self.logger.error(e)
        return users

    async def get_chat_admins(self, chat):
        return await self.get_chat_users(chat, admin=True)

    def _unpack_forum_topic(self, topic):
        if isinstance(topic, ForumTopicDeleted):
            meta = {'id': topic.id}
            print('Deleted Forum Topic:', meta)
        else:
            meta = {'id': topic.id, 'date': unpack_datetime(topic.date), 'name': topic.title}
        # TODO from_id
        return meta

    async def get_chats_topics(self, chat):
        try:
            chat = int(chat)
        except (TypeError, ValueError):
            pass
        # chat = await self.client.get_entity(chat)
        topics = await self.client(GetForumTopicsRequest(channel=chat, offset_date=None, offset_id=0, offset_topic=0, limit=0))
        chat_topic = {}
        for topic in topics.topics:
            chat_topic[topic.id] = self._unpack_forum_topic(topic)
        if 1 not in chat_topic:
            chat_topic[1] = {'id': 1, 'date': self.chats[chat]['date'], 'name': 'General'}
        return chat_topic

    async def get_chat_recommendations(self, chat):
        chats = await self.client(GetChannelRecommendationsRequest(channel=chat))
        # if isinstance(chats, ChatsSlice):
        chats = chats.chats
        l_chats = []
        for chat in chats:
            l_chats.append(self._unpack_get_chat(chat))
        return l_chats

    async def search_contact(self, to_search, limit=None):
        entities = []
        try:
            res = await self.client(SearchRequest(to_search, limit=100))
            if res:
                for chat in res.chats:
                    entities.append(self._unpack_get_chat(chat))
                for user in res.users:
                    entities.append(self._unpack_get_chat(user))
        except QueryTooShortError:
            self.logger.error(f'The query string is too short: {to_search}')
            sys.exit(0)
        except SearchQueryEmptyError:
            self.logger.error(f'The search query is empty')
            sys.exit(0)
        except TimeoutError:
            self.logger.error(f'A timeout occurred while fetching data from the worker')
            sys.exit(0)
        return entities

    # TODO LIST / JOIN NEW ADDED CHATS
    async def get_chats_folder_list(self, folder_code):  # TODO Check slug length ???
        meta = {'chats': []}
        try:
            c_list = await self.client(CheckChatlistInviteRequest(slug=folder_code))
            if isinstance(c_list, ChatlistInvite):
                if c_list.chats:
                    meta['name'] = c_list.title
                if c_list.peers:
                    for peers in c_list.peers:
                        # print(await self.client.get_entity(peers))
                        chat_meta = await self.get_entity(peers, load_dialog=False)
                        if not chat_meta:
                            chat_meta = self._unpack_peer(peers)
                        meta['chats'].append(chat_meta)
                # print(c_list.emoticon)  # list emoticon
                # print(c_list.chats) # meta chat -> can be empty
                # print(c_list.users) # meta user

            elif isinstance(c_list, ChatlistInviteAlready):
                # local ID: c_list.filter_id
                for peers in c_list.missing_peers:  # TODO LIST / JOIN NEW ADDED CHATS
                    chat_meta = await self.get_entity(peers, load_dialog=False)
                    if not chat_meta:
                        chat_meta = self._unpack_peer(peers)
                    meta['chats'].append(chat_meta)

                for peers in c_list.already_peers:
                    chat_meta = await self.get_entity(peers, load_dialog=False)
                    if not chat_meta:
                        chat_meta = self._unpack_peer(peers)
                    meta['chats'].append(chat_meta)
                # print(c_list.chats)
                # print(c_list.users)

        except BadRequestError as e:
            if e.message == 'INVITE_SLUG_EMPTY':
                self.logger.error(f'The specified chat folder/list is empty.')
            elif e.message == 'INVITE_SLUG_EXPIRED':
                self.logger.error(f'The specified chat folder/list has expired or is invalid.')
            else:
                self.logger.error(str(e))
            sys.exit(0)
        return meta

    async def _get_profile_photo(self, photo):
        pass

    def _unpack_bot_command(self, bot_commands):
        commands = []
        for command in bot_commands:
            commands.append({'command': command.command, 'description': command.description})
        return commands

    def _get_bot_info(self, bot_info):
        meta = {}
        if bot_info.user_id:
            meta['id'] = bot_info.user_id
        if bot_info.description:
            meta['info'] = bot_info.description
        if bot_info.commands:
            meta['commands'] = self._unpack_bot_command(bot_info.commands)
        return meta

    # TODO CHAT USERNAME - ACCESS HASH
    async def get_chat_full(self, chat, image=True):
        meta = {'id': chat.id}
        if isinstance(chat, Channel):
            full = await self.client(GetFullChannelRequest(chat))
        elif isinstance(chat, Chat):
            full = await self.client(GetFullChatRequest(chat.id))
        else:
            return

        full_chat = full.full_chat
        chats = full.chats
        users = full.users
        # print(chats)
        # print(users)
        # print(full.stringify())

        if full_chat.linked_chat_id:
            linked_chat = full_chat.linked_chat_id
        else:
            linked_chat = None

        for rel_chat in chats:
            if rel_chat.id == chat.id:
                meta = self._unpack_get_chat(rel_chat)

            if rel_chat.id == linked_chat:
                meta['discussion'] = {}
                if rel_chat.broadcast:
                    meta['discussion']['chat'] = chat.id
                    meta['discussion']['channel'] = rel_chat.id
                else:
                    meta['discussion']['chat'] = rel_chat.id
                    meta['discussion']['channel'] = chat.id

        # Unpack FULL Chat
        meta['info'] = full_chat.about

        if image and full_chat.chat_photo:
            try:
                icon = await asyncio.wait_for(self.client.download_profile_photo(full_chat, file=bytes), 30)
            except asyncio.exceptions.TimeoutError:
                print('TIMEOUT')
                try:
                    icon = await asyncio.wait_for(self.client.download_profile_photo(full_chat, file=bytes, download_big=False), 60)
                except asyncio.exceptions.TimeoutError:
                    icon = None
                    print('TIMEOUT Small photo')
            if icon:
                meta['icon'] = base64.standard_b64encode(icon).decode()

        if isinstance(full_chat, ChannelFull):
            meta['stats'] = {}
            if full_chat.participants_count:
                meta['stats']['participants'] = full_chat.participants_count
            if full_chat.admins_count:
                meta['stats']['admins'] = full_chat.admins_count
            if full_chat.banned_count:
                meta['stats']['banned'] = full_chat.banned_count
            if full_chat.online_count:
                meta['stats']['online'] = full_chat.online_count

            # TODO
            # print(full_chat.location)
            # print(full_chat.stories)
            # print('linked', full_chat.linked_chat_id)

        else:
            pass
            # print(full_chat.participants)
            # chat_photo optionnal

        # bot info
        if full_chat.bot_info:
            meta['bots'] = []
            for bot in full_chat.bot_info:
                meta['bots'].append(self._get_bot_info(bot))

            # participants
            # chat_photo
            # bot_info
            # pinned_msg_id

            # users => bots

        return meta

    async def get_private_chat_meta(self, chat, image=True):
        meta = self._unpack_get_chat(chat)
        if image and chat.photo:
            try:
                icon = await asyncio.wait_for(self.client.download_profile_photo(chat, file=bytes), 30)
            except asyncio.exceptions.TimeoutError:
                print('TIMEOUT')
                try:
                    icon = await asyncio.wait_for(self.client.download_profile_photo(chat, file=bytes, download_big=False), 40)
                except asyncio.exceptions.TimeoutError:
                    icon = None
                    print('TIMEOUT Small photo')
            if icon:
                meta['icon'] = base64.standard_b64encode(icon).decode()
        return meta

    # Get Chat metas
    async def get_chat_meta(self, chat=None):
        if isinstance(chat, User):
            meta = await self.get_user_meta(chat)
        else:
            if chat.id not in self.chats:
                try:
                    self.chats[chat.id] = await self.get_chat_full(chat)
                except ChannelPrivateError:
                    self.chats[chat.id] = await self.get_private_chat_meta(chat)
            meta = self.chats[chat.id]

            if isinstance(chat, Channel):
                # TODO -> refresh subchannels list on watch -> get new channels creation
                if chat.forum:
                    # Save Forum topics in CACHE
                    if chat.id not in self.subchannels:
                        self.subchannels[chat.id] = await self.get_chats_topics(chat.id)
                    meta['subchannels'] = list(self.subchannels[chat.id].values())
        return meta

    def get_message_subchannel(self, chat_id, message, meta):  # chat.id
        # TODO USE subchannel_IDS DICT
        # Get Message Subchannel. General topic ID = 1
        if 'reply_to' not in meta:
            # if 1 in self.subchannels[chat.id]: # TODO raise Exception
            meta['chat']['subchannel'] = self.subchannels[chat_id][1]
        elif not message.reply_to.forum_topic:
            # if 1 in self.subchannels[chat.id]:  # TODO raise Exception
            meta['chat']['subchannel'] = self.subchannels[chat_id][1]
        elif message.reply_to.reply_to_top_id:
            # if message.reply_to.reply_to_top_id in self.subchannels[chat.id]:
            meta['chat']['subchannel'] = self.subchannels[chat_id][message.reply_to.reply_to_top_id]
        else:
            if meta['reply_to']['message_id'] in self.subchannels[chat_id]:
                meta['chat']['subchannel'] = self.subchannels[chat_id][meta['reply_to']['message_id']]
                del meta['reply_to']
        if not meta['chat']['subchannel']:
            print(meta)
            sys.exit(0)  # TODO raise exception
        return meta

    # TODO metas
    # photo
    # channel type
    def _unpack_channel(self, channel):
        if channel.id in self.chats:
            meta = self.chats[channel.id]
        else:
            meta = {}
        meta['id'] = channel.id
        meta['name'] = channel.title
        meta['date'] = unpack_datetime(channel.date)
        meta['type'] = 'channel'  # TODO add broadcast, supergroup type ???
        if channel.username:
            meta['username'] = channel.username.lower()
        if channel.access_hash:
            meta['access_hash'] = channel.access_hash
        return meta

    # TODO metas
    # photo
    # version
    # migrated to
    def _unpack_chat(self, chat):
        if chat.id in self.chats:
            meta = self.chats[chat.id]
        else:
            meta = {}
        meta['id'] = chat.id
        meta['name'] = chat.title
        meta['date'] = unpack_datetime(chat.date)
        meta['type'] = 'chat'
        meta['participants'] = 'participants_count'
        return meta

    # TODO metas
    # photo
    def _unpack_user(self, user):
        if user.id in self.users:
            meta = self.users[user.id]
        else:
            meta = {}
        meta['id'] = user.id
        meta['type'] = 'user'
        if user.username:
            meta['username'] = user.username.lower()
        if user.first_name:
            meta['first_name'] = user.first_name
        if user.last_name:
            meta['last_name'] = user.last_name
        if user.phone:
            meta['phone'] = user.phone
        if user.access_hash:
            meta['access_hash'] = user.access_hash
        return meta

    # TODO Chat/Channel/User Photo
    def _unpack_get_chat(self, chat):
        if isinstance(chat, Channel):
            return self._unpack_channel(chat)
        elif isinstance(chat, Chat):
            return self._unpack_chat(chat)
        elif isinstance(chat, User):
            return self._unpack_user(chat)

    def _unpack_peer(self, peer):
        meta = {}
        if isinstance(peer, PeerChannel):
            meta['id'] = peer.channel_id
            meta['type'] = 'channel'
        elif isinstance(peer, PeerChat):
            meta['id'] = peer.chat_id
            meta['type'] = 'chat'
        elif isinstance(peer, PeerUser):
            meta['id'] = peer.user_id
            meta['type'] = 'user'
        return meta

    async def unpack_sender(self, sender):
        if isinstance(sender, Channel):
            if sender.id not in self.chats:
                try:
                    self.chats[sender.id] = await self.get_chat_full(sender)
                except ChannelPrivateError:
                    self.chats[sender.id] = await self.get_private_chat_meta(sender)
            return self.chats[sender.id]
        elif isinstance(sender, User):
            if sender.id not in self.users:
                self.users[sender.id] = await self.get_user(sender)
            return self.users[sender.id]

    # https://github.com/LonamiWebs/Telethon/blob/v1/telethon/extensions/markdown.py#L12
    def unpack_message_entities(self, message):
        # text = helpers.add_surrogate(message.raw_text)
        text = ''
        for ent, txt in message.get_entities_text():
            if isinstance(ent, MessageEntityTextUrl):
                text = text + f'\n[{txt}]({ent.url})'
            elif isinstance(ent, MessageEntityMentionName):
                text = text + f'\n[{txt}](tg://user?id={ent.user_id})'
        #         offset = ent.offset
        #         if offset > 0:
        #             offset = offset - 1
        #         length = ent.length
        #         print(ent)
        #         print(txt.encode())
        #         print(helpers.del_surrogate(text[offset:offset + length]))
        # text = helpers.del_surrogate(text)
        return text

    async def get_message_mentions(self, message, chat_id):
        mentions = {'chats': [], 'users': []}
        to_extract = False
        for entity in message.entities:
            # print(entity)
            if isinstance(entity, MessageEntityMention) or isinstance(entity, MessageEntityUrl):
                to_extract = True
            elif isinstance(entity, MessageEntityTextUrl):
                meta = await self.get_entity_meta_from_text(entity.url)
                if meta:
                    if meta['type'] == 'user':
                        mentions['users'].append(meta)
                    else:
                        mentions['chats'].append(meta)
            elif isinstance(entity, MessageEntityMentionName):
                # print(entity.user_id)
                meta = await self.get_entity_meta(entity.user_id, entity_type='id')
                if meta:
                    if meta['type'] == 'user':
                        mentions['users'].append(meta)
                    else:
                        mentions['chats'].append(meta)

        # print(message.get_entities_text())
        if to_extract:
            for extracted in message.get_entities_text():
                if isinstance(extracted[0], MessageEntityMention):
                    # print('extracted: ', extracted[1])
                    print('TO CHECK IF IS ID:', extracted[1])
                    time.sleep(1)

                    meta = await self.get_entity_meta_from_text(extracted[1])
                    if meta:
                        if meta['type'] == 'user':
                            mentions['users'].append(meta)
                        else:
                            mentions['chats'].append(meta)
                elif isinstance(extracted[0], MessageEntityUrl):
                    # print(extracted[1])
                    meta = await self.get_entity_meta_from_text(extracted[1])
                    if meta:
                        if meta['type'] == 'user':
                            mentions['users'].append(meta)
                        else:
                            mentions['chats'].append(meta)
        # print()
        # print(json.dumps(mentions, indent=4))
        # print(mentions)
        if mentions['chats'] or mentions['users']:
            # remove self mention
            to_remove = None
            for key in mentions['chats']:
                if key['id'] == chat_id:
                    to_remove = key
            if to_remove:
                mentions['chats'].remove(to_remove)
            return mentions

    # poll:
    # status (open, closed)
    # date import ????
    # multiple answers
    def _unpack_poll(self, poll):
        print()
        p = poll.poll
        meta = {'id': p.id, 'question': p.question, 'answers': []}
        dirct_answers = {}
        for answers in p.answers:
            dirct_answers[answers.option] = {'answer': answers.text}

        if poll.results.total_voters:
            meta['votes'] = poll.results.total_voters

        if poll.results.results:
            for a_res in poll.results.results:
                dirct_answers[a_res.option]['votes'] = a_res.voters
                # chosen
                # correct

        for k in dirct_answers.keys():
            meta['answers'].append(dirct_answers[k])

        # print()
        # print(poll)
        # print()
        # print(poll.poll)
        # print()
        # print(poll.results)
        # print(json.dumps(meta, indent=2))
        # sys.exit(0)
        return meta

    def _unpack_media_meta(self, message):
        meta = {}
        file = message.file
        if file:
            # meta['id'] = file.id
            name = file.name
            if name:  ####
                meta['name'] = name
            else:
                meta['name'] = ''
            ext = file.ext
            if ext:
                meta['ext'] = ext
            mime_type = file.mime_type
            if mime_type:
                meta['mime_type'] = mime_type
            size = file.size
            if size:  # size in bytes
                meta['size'] = size

            # message.document.file_reference ?
            # message.photo.file_reference ?

        # poll
        poll = message.poll
        if poll:
            meta = self._unpack_poll(poll)
        return meta

    async def _download_media(self, message):
        try:
            media_content = await message.download_media(file=bytes, progress_callback=callback_download)
        except ValueError as e:
            print(e)
            media_content = None
        return media_content

    async def get_media(self, obj_json, message, download=False, save_dir=''):  # TODO save dir + size limit
        # file: photo + document (audio + gif + sticker + video + video_note + voice)

        if download and message.file:
            t_mime_type = obj_json['meta']['media'].get('mime_type')
            if t_mime_type:
                tm_type, tm_subtype = t_mime_type.split('/')
            else:
                tm_type = None
                tm_subtype = None
            # TODO verify real mimetype -> none mimetype
            if message.file.size < 50000000:  # bytes   # TODO UP TO 50 MB ???
                if tm_type == 'application' or tm_type == 'text':
                    if tm_subtype in DOWNLOAD_MIMETYPES[tm_type]:
                        # TODO LIMIT PDF SIZE
                        media_content = await self._download_media(message)
                        # print(media_content)
                        if media_content:
                            if tm_subtype == 'pdf':
                                print('pdf')
                                obj_media_meta = dict(obj_json)
                                obj_media_meta['meta']['type'] = 'pdf'
                                data_sha256 = sha256(media_content).hexdigest()
                                name = uuid4()
                                pdf_file = f'/tmp/{name}.pdf'
                                with open(pdf_file, 'wb') as f:
                                    f.write(media_content)
                                file_metadata = extract_file_metadata(pdf_file)
                                if file_metadata:
                                    obj_media_meta['meta']['file_metadata'] = file_metadata
                                media_content = convert_pdf_to_pdfa(media_content)

                                if self.ails:
                                    self.send_to_ail(media_content, obj_media_meta['meta'], data_sha256=data_sha256)

                            else:
                                # Check incorrect File Mimetype
                                if t_mime_type == 'text/plain' and len(media_content) > 100:
                                    mimetype = _get_file_mimetype(media_content[:100])
                                else:
                                    mimetype = _get_file_mimetype(media_content)
                                # print(t_mime_type, mimetype)
                                m_type, m_subtype = mimetype.split('/')
                                if m_type == 'application' or m_type == 'text':
                                    if m_subtype in DOWNLOAD_MIMETYPES[m_type]:
                                        obj_media_meta = dict(obj_json)
                                        obj_media_meta['meta']['type'] = 'text'

                                        if self.ails:
                                            self.send_to_ail(media_content, obj_media_meta['meta'])
                                        # print(json.dumps(obj_media_meta, indent=4, sort_keys=True))

                elif tm_type == 'image':
                    media_content = await self._download_media(message)
                    if media_content:
                        # Check File Mimetype
                        mimetype = _get_file_mimetype(media_content)
                        m_type, m_subtype = mimetype.split('/')
                        if m_type == 'image':
                            obj_media_meta = dict(obj_json)
                            obj_media_meta['meta']['type'] = 'image'

                            if self.ails:
                                self.send_to_ail(media_content, obj_media_meta['meta'])
                            # print(json.dumps(obj_media_meta, indent=4, sort_keys=True))

            if save_dir:  # TODO GET FILE HASH
                if not os.path.exists(save_dir):
                    os.makedirs(save_dir)
                media_content = await message.download_media(file=save_dir, progress_callback=callback_download)
                # print(meta)

        # message.geo
        # message.media
        # if message.media:
        #     print(message.media)

        # if message.document:  # /!\ don't filter sticker ...
        #     # path = await message.download_media()
        #     print(message.document)

        # message.audio
        # message.gif
        # message.video
        # message.video_note
        # message.voice
        # message.web_preview
        # if message.photo:
        #     path = await message.download_media()
        #     print(path)

    # option: get_reply_message ????
    # message.geo
    async def _process_message(self, message, download=False, save_dir=None, replies=True, mark_read=False, chat_meta={}, parent_message_id=None):
        print(message)
        if not message:
            return {}
        # post
        # pinned
        mess = self._get_default_dict()
        if message.message:
            mess['data'] = message.message
        else:  # media if '' or MessageService if None
            mess['data'] = ''
        meta = mess['meta']
        meta['id'] = message.id
        meta['date'] = unpack_datetime(message.date)
        if message.edit_date:
            meta['edit_date'] = unpack_datetime(message.edit_date)
        if message.media:
            meta['media'] = self._unpack_media_meta(message)
        if message.views:
            meta['views'] = message.views

        if message.ttl_period:
            meta['expire'] = message.ttl_period

        # message.peer_id The peer to which this message was sent
        # message.from_id The peer who sent this message. None for anonymous message

        if message.reply_to:
            # reply_to.reply_to_peer_id ?

            reply_meta = {}
            # THREAD
            if replies and chat_meta:
                meta['thread'] = {}
                # reply_to_msg_id set to thread ID if not a reply.
                if message.reply_to.reply_to_top_id:
                    # meta['thread']['id'] = message.reply_to.reply_to_top_id
                    meta['thread']['id'] = parent_message_id
                    reply_meta['message_id'] = message.reply_to.reply_to_msg_id
                else:
                    # meta['thread']['id'] = message.reply_to.reply_to_msg_id
                    meta['thread']['id'] = parent_message_id
                meta['thread']['parent'] = {}
                meta['thread']['parent']['chat'] = chat_meta['id']
                if chat_meta.get('subchannel'):
                    meta['thread']['parent']['subchannel'] = chat_meta['subchannel']['id']
                meta['thread']['parent']['message'] = meta['thread']['id']
            else:
                reply_meta['message_id'] = message.reply_to.reply_to_msg_id
            meta['reply_to'] = reply_meta
            # print(meta['reply_to'])
            # print(message.stringify())
            # sys.exit(0)

        # Message comment original chat: Already Extracted in previous message
        if chat_meta:
            meta['chat'] = chat_meta
        else:
            chat = await message.get_chat()
            meta['chat'] = await self.get_chat_meta(chat=chat)

            if 'subchannels' in meta['chat'] and not isinstance(message, MessageService):
                self.get_message_subchannel(chat.id, message, meta)

            # chat = await message.get_chat() # TODO HANDLE USER CHAT ################################################################
            # if chat:
            #     if chat.id not in self.chats and not isinstance(chat, User):
            #         self.chats[chat.id] = await self.get_chat_full(chat)
            #
            #     meta['chat'] = self._unpack_get_chat(chat)
            #
            #     if isinstance(chat, Channel):
            #         # TODO -> refresh subchannels list on watch -> get new channels creation
            #         if chat.forum:
            #             if chat.id not in self.subchannels:
            #                 self.subchannels[chat.id] = await self.get_chats_topics(chat.id)
            #
            #             meta['chat']['subchannels'] = list(self.subchannels[chat.id].values())
            #             # print(json.dumps(meta['chat']['subchannels']))
            #
            #             self.get_message_subchannel(chat.id, message, meta)
            #
            #             #####
            #             # # TODO USE subchannel_IDS DICT
            #             # # General topic, ID = 1
            #             # if 'reply_to' not in meta:
            #             #     # if 1 in self.subchannels[chat.id]: # TODO raise Exception
            #             #     meta['chat']['subchannel'] = self.subchannels[chat.id][1]
            #             # elif not message.reply_to.forum_topic:
            #             #     # if 1 in self.subchannels[chat.id]:  # TODO raise Exception
            #             #     meta['chat']['subchannel'] = self.subchannels[chat.id][1]
            #             # elif message.reply_to.reply_to_top_id:
            #             #     # if message.reply_to.reply_to_top_id in self.subchannels[chat.id]:
            #             #     meta['chat']['subchannel'] = self.subchannels[chat.id][message.reply_to.reply_to_top_id]
            #             # else:
            #             #     if meta['reply_to']['message_id'] in self.subchannels[chat.id]:
            #             #         meta['chat']['subchannel'] = self.subchannels[chat.id][meta['reply_to']['message_id']]
            #             #         del meta['reply_to']
            #             # if not meta['chat']['subchannel']:
            #             #     print(meta)
            #             #     sys.exit(0)  # TODO raise exception
            #             ######

        sender = await message.get_sender()
        if sender:
            meta['sender'] = await self.unpack_sender(sender)
        else:
            message_chat_id = meta['chat']['id']
            meta['sender'] = {'id': message_chat_id, 'type': 'chat'}
            if meta['chat'].get('username'):
                meta['sender']['username'] = meta['chat']['username']
            if meta['chat'].get('name'):
                meta['sender']['first_name'] = meta['chat']['name']

            if not meta['sender'].get('username') and meta['chat'].get('name'):
                meta['sender']['username'] = meta['chat']['name']

            if 'icon' in self.chats[message_chat_id]:
                meta['sender']['icon'] = self.chats[message_chat_id]['icon']
            if 'info' in self.chats[message_chat_id]:
                meta['sender']['info'] = self.chats[message_chat_id]['info']

        # if message.entities: # TODO ################# REMOVE ME #############################################################################
        #     mess_entities = self.unpack_message_entities(message)
        #     if mess_entities:
        #         mess['data'] = mess['data'] + '\n' + mess_entities

        #

        ## FORWARD ##

        if message.forwards:  # The number of times this message has been forwarded.
            meta['forwards'] = message.forwards
        # https://stackoverflow.com/a/75978777
        if message.forward:  # message.fwd_from
            meta['forward'] = {}
            meta['forward']['date'] = unpack_datetime(message.forward.date)
            if message.forward.from_id:  # original channel or user ID  # TODO DIFF User/CHATS
                meta['forward']['from'] = self._unpack_peer(message.forward.from_id)
            if message.forward.from_name:
                meta['forward']['from_name'] = message.forward.from_name
            if message.forward.channel_post:  # original message ID
                meta['forward']['channel_post'] = message.forward.channel_post
            if message.forward.post_author:
                meta['forward']['post_author'] = message.forward.post_author
            if message.forward.saved_from_msg_id:  # previous source message ID
                meta['forward']['saved_from_msg_id'] = message.forward.saved_from_msg_id
            if message.forward.saved_from_peer:  # previous source chat/user ID
                meta['forward']['saved_from_peer'] = self._unpack_peer(message.forward.saved_from_peer)

            ## GET CHAT Forwarded from meta ##

            # print(type(message.forward))
            # print(message.forward.chat)
            # print(message.forward.sender)

            # TODO Check forward flag/option
            if message.forward.chat:  # TODO Check forward flag/option            # TODO LOGS
                forward_chat = await self.get_chat_meta(chat=message.forward.chat)
                if forward_chat:
                    meta['forward']['chat'] = forward_chat
            #
            # # TODO USER MESSAGE FORWARDED
            if message.forward.sender:
                forward_user = await self.unpack_sender(message.forward.sender)
                if forward_user:
                    meta['forward']['user'] = forward_user

        # -FORWARD- #

        # MENTIONS #
        elif message.entities and self.extract_mentions:
            mentions = await self.get_message_mentions(message, meta['chat']['id'])
            if mentions:
                meta['mentions'] = mentions

        if message.reactions:
            meta['reactions'] = []
            # print(message.reactions.can_see_list)  # TO check
            # message.reactions.recent_reactions # to check activity
            for reaction_count in message.reactions.results:
                reaction = reaction_count.reaction
                if isinstance(reaction, ReactionEmoji):
                    reaction = reaction.emoticon
                elif isinstance(reaction, ReactionCustomEmoji):  # Fetch custom emoji ???
                    reaction = reaction.document_id
                elif isinstance(reaction, ReactionPaid):
                    reaction = '💳⭐'
                # TODO LOG ERROR unknown reactions
                meta['reactions'].append({'reaction': reaction, 'count': reaction_count.count})

        # mark as read
        if mark_read:
            await message.mark_read()

        if self.ails:
            if mess['data'] or meta.get('media'):
                mess['meta']['type'] = 'message'
                print()
                print(mess['data'])
                print()
                #print(json.dumps(mess['meta']))
                self.send_to_ail(mess['data'], mess['meta'])

        # print(mess)
        # print(json.dumps(mess, indent=4, sort_keys=True))
        # sys.exit(0)

        # Download medias
        if meta.get('media'):
            # if meta['media']['name']:
            #     print(meta['media'])
            #     if meta['media']['mime_type'].startswith('image'):
            #         print(meta['media'])
            #         sys.exit(0)

            # TODO Multiple medias ??????
            await self.get_media(mess, message, download=download, save_dir=save_dir)

        # Downloads comments
        if message.replies and replies:
            if message.replies.replies > 0:
                await self.get_message_replies(message.chat, message.id, meta['chat'])

    async def get_message_replies(self, chat, message_id, chat_meta): # TODO Downloads files
        # chat = await self.get_entity(chat, r_id=True)
        async for message in self.client.iter_messages(chat, reply_to=message_id):
            # print(message)
            # print()
            await self._process_message(message, chat_meta=chat_meta, parent_message_id=message_id)

    async def get_chat_messages(self, chat, download=False, save_dir=None, replies=False, min_id=0, max_id=0, limit=None, mark_read=False):
        chat = await self.get_entity(chat, r_id=True)
        if not chat:
            pending = asyncio.all_tasks(self.client.loop)
            for task in pending:
                task.cancel()
        else:
            async for message in self.client.iter_messages(chat, min_id=min_id, max_id=max_id, filter=None, limit=limit):
                # print(message)
                # print()
                mess = await self._process_message(message, replies=replies, mark_read=mark_read, download=download, save_dir=save_dir)

    async def get_unread_message(self, download=False, save_dir=None, replies=False):
        async for dialog in self.client.iter_dialogs():
            if not dialog.is_user:
                nb_unread = dialog.unread_count
                if nb_unread:
                    await self.get_chat_messages(dialog.entity, download=download, save_dir=save_dir, replies=replies, limit=nb_unread, mark_read=True)

    async def _process_deleted_message(self, chat_id, l_message_id):
        chat = await self.get_entity(chat_id)
        print(chat)
        for message_id in l_message_id:
            print(message_id)
        print()

    # TODO filter chats
    async def monitor_chats(self, download=False, save_dir=None):
        # subscribe to NewMessage event
        @self.client.on(events.NewMessage)  # NewMessage(incoming=True)
        async def new_message_handler(event):
            # filter event
            await self._process_message(event.message, download=download, save_dir=save_dir)

        @self.client.on(events.MessageDeleted)
        async def new_message_deleted(event):
            print(event)
            await self._process_deleted_message(event.chat_id, event.deleted_ids)

            # Log all deleted message IDs
            for msg_id in event.deleted_ids:
                print('Message', msg_id, 'was deleted in', event.chat_id)
                # Message 208882 was deleted in -1001228309110

        @self.client.on(events.MessageEdited)
        async def new_message_edited(event):
            # TODO same as a new message
            print('Message', event.id, 'changed at', event.date)

def unpack_datetime(datetime_obj):
    date_dict = {'datestamp': datetime.strftime(datetime_obj, '%Y-%m-%d %H:%M:%S'),
                 'timestamp': datetime_obj.timestamp(),
                 'timezone': datetime.strftime(datetime_obj, '%Z')}
    return date_dict


def sanityze_message_id(mess_id):
    try:
        mess_id = int(mess_id)
        if mess_id > 0:
            return mess_id
        else:
            return 0
    except (TypeError, ValueError):
        return 0


# Printing download progress
def callback_download(current, total):
    print('Downloaded', current, 'out of', total,
          'bytes: {:.2%}'.format(current / total))


# message.entities
### BEGIN - MESSAGE ENTITY ###  UTF 16 code-unit
# def _get_entity_str(data, entity):
#     entity_start = entity.offset
#     entity_stop = entity.offset + entity.length
#     return data[entity_start:entity_stop]
#
# # error offset with smiley
# def unpack_entity(dict_meta, data, entity):
#     if isinstance(entity, MessageEntityUrl):
#         str_entity = _get_entity_str(data, entity)
#         dict_meta['urls'].append(str_entity)
#     # <a></a>
#     elif isinstance(entity, MessageEntityTextUrl):
#         str_entity = _get_entity_str(data, entity)
#         dict_meta['urls'].append(entity.url)
#     elif isinstance(entity, MessageEntityMention):
#         str_entity = _get_entity_str(data, entity)
#         dict_meta['mentions'].append(str_entity)
#         # print('---')
#         # print(str_entity)
#         # print(entity.offset)
#         # print(entity.length)
#     else:
#         pass
#         # print('000 000')
#         # print(type(entity))
#         # print(_get_entity_str(data, entity))
#         # print('000 000')
#
#     # MessageEntityMention
#     # MessageEntityEmail
#     # MessageEntityPhone ?
#     # MessageEntityCode ???

### --- END - MESSAGE ENTITY ---###

# TODO SAVE JSON OPTION

# TODO JOIN via file list
# TODO Try to export joined chats

# TODO + AIL if plus == invite

# if __name__ == '__main__':
#     t = ''
#     r = parse_entity(t)
#     print(r)
