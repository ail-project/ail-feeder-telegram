#!/usr/bin/env python3
# -*-coding:UTF-8 -*

import os
import sys

from datetime import datetime

from telethon import TelegramClient
from telethon.tl.functions.channels import JoinChannelRequest, LeaveChannelRequest

from telethon.tl.types import Channel, User, ChannelParticipantsAdmins, PeerUser, PeerChat, PeerChannel
from telethon.tl.types import MessageEntityUrl, MessageEntityTextUrl, MessageEntityMention
from telethon.tl.types import Chat, ChatEmpty
from telethon.tl.types import ChatInvite, ChatInviteAlready #, ChatInvitePeek
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.functions.messages import CheckChatInviteRequest

# errors
from telethon.errors.rpcerrorlist import ChatAdminRequiredError, UserNotParticipantError
from telethon.errors.rpcerrorlist import InviteHashExpiredError, InviteHashInvalidError
from telethon.errors.common import MultiError

async def get_current_channels(client):
    all_channels_id = []
    async for dialog_obj in client.iter_dialogs():
        if not dialog_obj.is_user:
            channel_id = int(dialog_obj.id)
            # negative: is a group, positive: single person
            all_channels_id.append(channel_id)
    return all_channels_id

async def get_channel_admins(client, channel):
    try:
        async for user in client.iter_participants(channel, filter=ChannelParticipantsAdmins):
            print(user)
    except ChatAdminRequiredError:
        print(f'Error, {channel}: Chat admin privileges required')

async def get_channel_all_users(client, channel):
    all_channel_users = []
    try:
        async for user in client.iter_participants(channel, aggressive=True):
            #print(user)
            res = unpack_user(user)
            print(res)
            all_channel_users.append(res)
    except MultiError as e:
        if isinstance(e.exceptions[0], ChatAdminRequiredError):
            print(f'Error, {channel}: Chat admin privileges required')
        else:
            print(e)
    print(len(all_channel_users))
    return all_channel_users


def unpack_datetime(datetime_obj):
    date_dict = {}
    date_dict['datestamp'] = datetime.strftime(datetime_obj, '%Y-%m-%d')
    date_dict['timestamp'] = datetime.strftime(datetime_obj, '%H:%M:%S')
    date_dict['timezone'] = datetime.strftime(datetime_obj, '%Z')
    return date_dict

# Chat = Chat + Channel + ChannelForbidden + ChatEmpty + ChatForbidden
# # TODO: support ChannelForbidden (access_hash ?)
def unpack_chat(chat_obj):
    # ChatEmpty
    dict_chat = {'id': chat_obj.id}
    chat_type = type(chat_obj)
    if chat_type == ChatEmpty:
        return dict_chat
    # ChannelForbidden + ChatForbidden
    dict_chat['title'] = chat_obj.title

    if chat_type == Chat or chat_type == Channel:
        dict_chat['version'] = chat_obj.version
        dict_chat['date'] = unpack_datetime(chat_obj.date)
        if chat_obj.participants_count is not None:
            dict_chat['nb_participants'] = chat_obj.participants_count

        if chat_type == Channel:
            dict_chat['username'] = chat_obj.username
            if chat_obj.megagroup is not None:
                dict_chat['megagroup'] = chat_obj.megagroup
                # verified ??
    return dict_chat

# ChatInvite, ChatInvitePeek, ChatInviteAlready
def unpack_chat_invite(chat_invite):
    chat_invite_type = type(chat_invite)
    dict_chat = {}
    if chat_invite_type == ChatInvite:

        dict_chat = {'title': chat_invite.title,
                        'nb_participants': chat_invite.participants_count}
        #if chat_invite.participants:
        #    dict_channel['users'] = chat_invite.participants
        if chat_invite.channel is not None:
            dict_chat['is_channel'] = chat_invite.channel
        if chat_invite.public is not None:
            dict_chat['public'] = chat_invite.public # # TODO: remove ??????
        if chat_invite.broadcast is not None:
            dict_chat['broadcast'] = chat_invite.broadcast
        if chat_invite.megagroup is not None:
            dict_chat['megagroup'] = chat_invite.megagroup
    # ChatInvitePeek, ChatInviteAlready
    else:
        dict_chat = unpack_chat(chat_invite.chat)
        # # TODO:  ChatInvitePeek => expires ???
    return dict_chat

# User, UserEmpty
def unpack_user(user_obj):
    dict_user = {'id': user_obj.id}
    user_type = type(user_obj)
    if user_type == User:
        if user_obj.username:
            dict_user['username'] = user_obj.username
        if user_obj.first_name:
            dict_user['first_name'] = user_obj.first_name
        if user_obj.last_name:
            dict_user['last_name'] = user_obj.last_name
        if user_obj.phone:
            dict_user['phone'] = user_obj.phone
    return dict_user

async def get_full_user_info(client, user_id):
    res = await client(GetFullUserRequest(id=user_id))
    return res

def sanityse_entity(entity):
    # entity id
    try:
        entity = int(entity)
    except:
        pass
    return entity

def sanityse_message_id(mess_id):
    try:
        mess_id = int(mess_id)
        if mess_id > 0:
            return mess_id
        else:
            return 0
    except:
        return 0

async def validate_join_code(client, join_code):
    try:
        invite_obj = await client(CheckChatInviteRequest(join_code))
        #print(chat_invite)
        print(type(invite_obj))
        if type(invite_obj) == ChatInvite:
            dict_channel = unpack_chat_invite(invite_obj)
        elif type(invite_obj) == ChatInviteAlready:
            dict_channel = unpack_chat(invite_obj.chat)
        print(dict_channel)
    except InviteHashExpiredError: # # TODO: add in logs
        print('Error: The chat the user tried to join has expired and is not valid anymore')
    except InviteHashInvalidError:
        print('Error: The invite hash is invalid')

# # TODO: check if already join + add exception
async def join_public_channel(client, channel_name):
    channel_entity = await client.get_entity(channel_name)
    res = await client(JoinChannelRequest(channel_entity))
    print(res)

async def leave_public_channel(client, channel_name):
    channel_entity = await client.get_entity(channel_name)
    try:
        res = await client(LeaveChannelRequest(channel_entity))
        print(res)
    except UserNotParticipantError: # # TODO: add in logs
        print('Error: This user is not a member of the specified megagroup or channel')

#async def join_private_channel(client, hash_id):
#    await client(ImportChatInviteRequest(hash_id))

############################################################################

# add parameters
# offset_date (datetime)
async def get_all_channel_messages(client, channel_id, pyail, min_id=0, max_id=0):
    # DEBUG:
    #print(channel_id)

    async for message in client.iter_messages(channel_id, min_id=min_id, max_id=max_id):
        dict_meta = {}
        data = message.message
        if not data:
            continue

        dict_meta['message_id'] = message.id
        dict_meta['geo'] = message.geo
        dict_meta['date'] = unpack_datetime(message.date)

        if message.input_chat:
            dict_meta['channel_id'] = message.input_chat.channel_id
        else:
            print(message)
            sys.exit(0)

        # to investigate (bot)
        #buttons = message.buttons

        sender_obj = message.sender
        # Channel semder
        if isinstance(sender_obj, Channel): ## TODO: get channel info # FIXME use Chat object
            dict_meta['channel'] = unpack_chat(sender_obj)
            #.get_participants
        # User sender
        elif isinstance(sender_obj, User):
            dict_meta['user'] = unpack_user(sender_obj)
            # # TODO: check if is bot

        # no sender object
        # forwaded messages
        else:
            pass
            print('------------------------------')
            print(message.fwd_from)
            #sys.exit(0)
            # # TODO: get message with channel_id + message_id => get sender

        ## Get extracted url + phone ##
        dict_meta['urls'] = []
        dict_meta['mentions'] = []
        if message.entities:
            for entity in message.entities:
                unpack_entity(dict_meta, data, entity)
        ## -- ##

        ## TODO:
        ## Get media (documents + images) ##
        # if message.media:
        #     # get media type
        #     media_type = next(iter(message.media.__dict__))
        #     media = getattr(message.media, media_type)
        #
        #     print(media_type)
        #     print(message.media)
        #     print(media)
        #
        #     if media_type == 'document':
        #         # get filename (need to iterate all attributes)
        #         file_name = [x for x in media.attributes if hasattr(x, "file_name")]
        #         if file_name:
        #             file_name = file_name[0].file_name
        #             print(file_name) # # TODO: add it in meta
        #             print(media.id)
        #             print(media.mime_type)
        #             print(media.size)
        #     print()
        ## -- ##

        #pyail.feed_json_item(data, dict_meta, 'ail_feeder_telegram', feeder_uuid)

        ## DEBUG ##
        #print(type(message))
        #print(json.dumps(dict_mess, indent=2, sort_keys=True))
        #print(message)
        print(data)
        print(dict_meta)
        print()
        ## -- ##

### BEGIN - MESSAGE ENTITY ###
def _get_entity_str(data, entity):
    entity_start = entity.offset
    entity_stop = entity.offset + entity.length
    return data[entity_start:entity_stop]

# # FIXME: error offset with smiley
def unpack_entity(dict_meta, data, entity):
    if isinstance(entity, MessageEntityUrl):
        str_entity = _get_entity_str(data, entity)
        dict_meta['urls'].append(str_entity)
    # <a></a>
    elif isinstance(entity, MessageEntityTextUrl):
        str_entity = _get_entity_str(data, entity)
        dict_meta['urls'].append(entity.url)
    elif isinstance(entity, MessageEntityMention):
        str_entity = _get_entity_str(data, entity)
        dict_meta['mentions'].append(str_entity)
        #print('---')
        #print(str_entity)
        #print(entity.offset)
        #print(entity.length)
    else:
        pass
        #print('000 000')
        #print(type(entity))
        #print(_get_entity_str(data, entity))
        #print('000 000')

    # MessageEntityMention
    # MessageEntityEmail
    # MessageEntityPhone ?
    # MessageEntityCode ???

### --- END - MESSAGE ENTITY ---###
