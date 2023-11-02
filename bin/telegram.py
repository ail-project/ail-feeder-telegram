#!/usr/bin/env python3
# -*-coding:UTF-8 -*

import json
import logging
import sys

from datetime import datetime

from libretranslatepy import LibreTranslateAPI

from telethon import TelegramClient, events
# from telethon import helpers

from telethon.tl.functions.channels import JoinChannelRequest, LeaveChannelRequest, GetForumTopicsRequest

from telethon.tl.types import Channel, User, ChannelParticipantsAdmins, PeerUser, PeerChat, PeerChannel
# from telethon.tl.types import MessageEntityUrl, MessageEntityTextUrl, MessageEntityMention
from telethon.tl.types import ReactionEmoji, ReactionCustomEmoji
from telethon.tl.types import Chat  # ChatEmpty
from telethon.tl.types import ChatInvite, ChatInviteAlready, ChatInvitePeek
from telethon.tl.functions.users import GetFullUserRequest  # https://tl.telethon.dev/constructors/users/user_full.html
# from telethon.tl.functions.messages import GetFullChatRequest  # chat_id=-00000000
# https://tl.telethon.dev/methods/messages/get_full_chat.html
# from telethon.tl.functions.channels import GetFullChannelRequest  # channel='username'
# https://tl.telethon.dev/methods/channels/get_full_channel.html
from telethon.tl.functions.messages import CheckChatInviteRequest, ImportChatInviteRequest
from telethon.tl.types import MessageEntityTextUrl, MessageEntityMentionName

# errors
from telethon.errors.rpcerrorlist import ChatAdminRequiredError  # UserNotParticipantError
from telethon.errors.rpcerrorlist import InviteHashExpiredError, InviteHashInvalidError
from telethon.errors import ChannelsTooMuchError, ChannelInvalidError, ChannelPrivateError, InviteRequestSentError
from telethon.errors import ChannelPublicGroupNaError, UserCreatorError, UserNotParticipantError, InviteHashEmptyError
from telethon.errors import UsersTooMuchError, UserAlreadyParticipantError, SessionPasswordNeededError
# from telethon.errors.common import MultiError

class TGFeeder:

    # dialog vs chats ???

    # ail_url ail_key ail_verifycert ail_feeder + disabled option
    def __init__(self, tg_api_id, tg_api_hash, session_name, ail_client=None):
        self.logger = logging.getLogger()  # TODO FORMAT LOGS

        self.source = 'ail_feeder_telegram'
        self.source_uuid = '9cde0855-248b-4439-b964-0495b9b2b8db'

        self.tg_api_id = int(tg_api_id)
        self.tg_api_hash = tg_api_hash
        self.session_name = session_name

        self.client = self.get_client()
        self.loop = self.client.loop

        if ail_client:
            self.ail = ail_client
        else:
            self.ail = False

        self.lt = LibreTranslateAPI("http://localhost:5000")

        self.subchannels = {}

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

    def translate(self, text):
        # get text language
        translation = ''
        lang = lt.detect(text)[0]
        if lang['confidence'] >= 50:
            translation = lt.translate(text, source=lang['language'], target='en')
        return translation

    async def get_chats(self, meta=True):  # TODO improve metas
        channels = []
        async for dialog_obj in self.client.iter_dialogs():
            # remove self chats
            if not dialog_obj.is_user:
                channel_id = dialog_obj.id
                # negative: is a group, positive: single person # TODO check chat id padding
                if meta:
                    channels.append(await self.get_entity(channel_id))
                else:
                    channels.append(channel_id)
        return channels

    def _unpack_invite(self, invite):
        meta = {}
        if isinstance(invite, ChatInvite):
            meta['title'] = invite.title
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

    async def join_chat(self, chat=None, invite=None):
        # join a public chat/channel
        # channel are a special form of chat
        if chat:
            try:
                chat = int(chat)
            except (TypeError, ValueError):
                pass
            chat = await self.client.get_entity(chat) # TODO
            try:
                updates = await self.client(JoinChannelRequest(chat))
                # print(updates)
                if updates:
                    meta = {}
                    if updates.chats:
                        meta = self._unpack_get_chat(updates.chats[0])
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
                if updates:
                    meta = {}
                    if updates.chats:
                        meta = self._unpack_get_chat(updates.chats[0])
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

    async def get_user(self, user):
        full = await self.client(GetFullUserRequest(id=user))
        meta_full = self._unpack_user_full(full.full_user)
        meta = self._unpack_user(full.users[0])  # TODO handle all mentioned users, chats
        if 'about' in meta_full:
            meta['about'] = meta_full['about']
        # print(meta)
        return meta

    # Note: entity ID: only work if is in a dialog or in the same chat, client.get_participants(group) need to be called
    #       -
    async def get_entity(self, entity, r_id=False):
        await self.client.get_dialogs()
        try:
            entity = int(entity)
        except (TypeError, ValueError):
            pass
        try:
            r = await self.client.get_entity(entity)
            entity = self._unpack_get_chat(r)
            if r_id:
                return entity['id']
            else:
                return entity
        except ValueError:
            self.logger.error(f'Could not find the entity {entity}')

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
                # print(user_meta)
        except ChatAdminRequiredError:
            self.logger.error(f'{chat.id}: Chat admin privileges required')
        # except MultiError as e:
        #     if isinstance(e.exceptions[0], ChatAdminRequiredError):
        #         self.logger.error(f'Error, {chat}: Chat admin privileges required')
        #     else:
        #         self.logger.error(e)
        return users

    async def get_chat_admins(self, chat):
        return await self.get_chat_users(chat, admin=True)

    def _unpack_forun_topic(self, topic):
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
        chat_topic = []
        for topic in topics.topics:
            chat_topic.append(self._unpack_forun_topic(topic))
        return chat_topic


    # TODO metas
    # photo
    # channel type
    def _unpack_channel(self, channel):
        meta = {'id': channel.id, 'title': channel.title, 'date': unpack_datetime(channel.date), 'type': 'channel'} # TODO add broadcast, supergroup type
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
        meta = {'id': chat.id, 'title': chat.title, 'date': unpack_datetime(chat.date), 'type': 'chat',
                'participants': chat.participants_count}
        return meta

    # TODO metas
    # photo
    def _unpack_user(self, user):
        # print(user)
        meta = {'id': user.id, 'type': 'user'}
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

    # TODO photo + bot_info
    def _unpack_user_full(self, userfull):
        meta = {'id': userfull.id, 'type': 'user'}
        if userfull.about:
            meta['about'] = userfull.about
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

    def _unpack_sender(self, sender):
        if isinstance(sender, Channel):
            return self._unpack_channel(sender)
        elif isinstance(sender, User):
            return self._unpack_user(sender)

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

    async def get_media(self, message, download=False):  # TODO save dir + size limit
        # file: photo + document (audio + gif + sticker + video + video_note + voice)
        meta = {}

        file = message.file
        if file:
            name = file.name
            if name: ####
                meta['name'] = name
            elif message.photo:
                meta['name'] = 'photo'
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

            if download:
                path = await message.download_media(file='downloads')  # file=bytes to save in memory
                # print(path)

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
        return meta

    # option: get_reply_message ????
    # message.geo
    async def _process_message(self, message, download=False, replies=True, mark_read=False, p_username=None):
        # print(message)
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
        if message.views:
            meta['views'] = message.views
        if message.forwards: # The number of times this message has been forwarded.
            meta['forwards'] = message.forwards
        # https://stackoverflow.com/a/75978777
        if message.forward:  # message.fwd_from
            meta['fwd_from'] = {}
            meta['fwd_from']['date'] = unpack_datetime(message.forward.date)
            if message.forward.from_id:
                meta['fwd_from']['from_id'] = self._unpack_peer(message.forward.from_id)
            if message.forward.from_name:
                meta['fwd_from']['from_name'] = message.forward.from_name
            if message.forward.channel_post:
                meta['fwd_from']['channel_post'] = message.forward.channel_post
            if message.forward.post_author:
                meta['fwd_from']['post_author'] = message.forward.post_author
            if message.forward.saved_from_msg_id:
                meta['fwd_from']['saved_from_msg_id'] = message.forward.saved_from_msg_id
            if message.forward.saved_from_peer:
                meta['fwd_from']['saved_from_peer'] = self._unpack_peer(message.forward.saved_from_peer)

        # message.peer_id The peer to which this message was sent
        # message.from_id The peer who sent this message. None for anonymous message

        if message.reply_to:
            # reply_to.reply_to_peer_id ?
            # reply_to.reply_to_top_id ?
            meta['reply_to'] = message.reply_to.reply_to_msg_id

        chat = await message.get_chat()
        if chat:
            meta['chat'] = self._unpack_get_chat(chat)
            if p_username:
                meta['chat']['username'] = p_username

            # TODO -> refresh subchannels list on watch -> get new channels creation
            if chat.forum:
                if not self.subchannels:
                    self.subchannels = await self.get_chats_topics(chat.id)

                meta['chat']['subchannels'] = self.subchannels  # TODO rename to sub-channel ????
                # print(json.dumps(meta['chat']['subchannels']))

                print()
                print(message)
                print()

                # TODO USE subchannel_IDS DICT
                # General topic, ID = 1
                if 'reply_to' not in meta:
                    for subchannel in self.subchannels:
                        if subchannel['id'] == 1:
                            meta['chat']['subchannel'] = subchannel
                            break
                elif not message.reply_to.forum_topic:
                    for subchannel in self.subchannels:
                        if subchannel['id'] == 1:
                            meta['chat']['subchannel'] = subchannel
                            break
                elif message.reply_to.reply_to_top_id:
                    for subchannel in self.subchannels:
                        if subchannel['id'] == message.reply_to.reply_to_top_id:
                            meta['chat']['subchannel'] = subchannel
                            break
                else:
                    for subchannel in self.subchannels:
                        if subchannel['id'] == meta['reply_to']:
                            meta['chat']['subchannel'] = subchannel
                            del meta['reply_to']
                            break
                # DEBUG
                # if 'subchannel' in meta['chat']:
                #     print('subchannel FOUND:        ', meta['chat']['subchannel'])
                # else:
                #     sys.exit(0)

        sender = await message.get_sender()
        if sender:
            meta['sender'] = self._unpack_sender(sender)

        if message.entities:
            mess_entities = self.unpack_message_entities(message)
            if mess_entities:
                mess['data'] = mess['data'] + '\n' + mess_entities

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
                meta['reactions'].append({'reaction': reaction, 'count': reaction_count.count})

        if message.replies:
            if message.replies.replies > 0:
                meta['replies'] = message.replies.replies
                if replies:
                    p_username = None
                    if meta.get('chat'):
                        if meta['chat'].get('username'):
                            p_username = meta['chat']['username']
                    await self.get_message_replies(chat, message.id, p_username=p_username)

        if message.media:
            media = await self.get_media(message, download=download)
            if media:
                meta['media'] = media
                # if not download: # TODO option ???
                #     media_mess = f"\n[File: {media.get('name', '')} {media.get('size', '')} B]"
                #     if media.get('mime_type'):
                #         media_mess += f" - {media.get('mime_type', '')}"
                #     mess['data'] = media_mess

        # mark as read
        if mark_read:
            await message.mark_read()

        if self.ail and mess['data']:  # TODO remove if media
            self.ail.feed_json_item(mess['data'], mess['meta'], self.source, self.source_uuid)
        # else:
        #     print(json.dumps(mess, indent=4, sort_keys=True))
        print(json.dumps(mess, indent=4, sort_keys=True))

    async def get_message_replies(self, chat, message_id, p_username=None):
        chat = await self.get_entity(chat, r_id=True)
        async for message in self.client.iter_messages(chat, reply_to=message_id):
            # print(message)
            # print()
            await self._process_message(message, p_username=p_username)

    async def get_chat_messages(self, chat, download=False, replies=False, min_id=0, max_id=0, limit=None, mark_read=False):
        messages = []
        # min_id = 1
        # max_id = 5
        # min_id = 171177
        # max_id = 171179
        # download = True
        chat = await self.get_entity(chat, r_id=True)
        async for message in self.client.iter_messages(chat, min_id=min_id, max_id=max_id, filter=None, limit=limit):
            # print(message)
            # print()
            mess = await self._process_message(message, replies=replies, mark_read=mark_read, download=download)

    async def get_unread_message(self, download=False, replies=False):
        async for dialog in self.client.iter_dialogs():
            if not dialog.is_user:
                nb_unread = dialog.unread_count
                if nb_unread:
                    await self.get_chat_messages(dialog.entity, download=download, replies=replies, limit=nb_unread, mark_read=True)

    # TODO filter chats
    async def monitor_chats(self):
        # subscribe to NewMessage event
        @self.client.on(events.NewMessage)  # NewMessage(incoming=True)
        async def new_message_handler(event):
            # filter event
            await self._process_message(event.message)

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

async def monitor_chats(client):
    return await client.monitor_chats()

# message.entities
### BEGIN - MESSAGE ENTITY ###
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
