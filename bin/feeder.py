#!/usr/bin/env python3
# -*-coding:UTF-8 -*

import argparse
import configparser
import os
import json
import sys

from datetime import datetime

import telegram
from pyail import PyAIL

from telethon import TelegramClient

# Check the configuration and do some preliminary structure checks
try:
    config = configparser.ConfigParser()
    config.read('../etc/conf.cfg')

    # Check AIL configuration, set variables and do the connection test to AIL API
    if not 'AIL' in config:
        print('[ERROR] The [AIL] section was not defined within conf.cfg. Ensure conf.cfg contents are correct.')
        sys.exit(0)

    try:
        # Set variables required for the Telegram Feeder
        feeder_uuid = config.get('AIL', 'feeder_uuid')
        ail_url = config.get('AIL', 'url')
        ail_key = config.get('AIL', 'apikey')
        ail_verifycert = config.getboolean('AIL', 'verifycert')
        ail_feeder = config.getboolean('AIL', 'ail_feeder')
    except Exception as e:
        print('[ERROR] Check ../etc/conf.cfg to ensure the following variables have been set:\n')
        print('[AIL] feeder_uuid \n')
        print('[AIL] url \n')
        print('[AIL] apikey \n')
        sys.exit(0)

    if ail_feeder:
        try:
            pyail = PyAIL(ail_url, ail_key, ssl=ail_verifycert)
        except Exception as e:
            print('[ERROR] Unable to connect to AIL Framework API. Please check [AIL] url, apikey and verifycert in '
                  '../etc/conf.cfg.\n')
            sys.exit(0)
    else:
        print('[INFO] AIL Feeder has not been enabled in [AIL] ail_feeder. Feeder script will not send output to AIL.\n')
        pyail = False
    # /End Check AIL configuration

    # Check Telegram configuration, set variables and do the connection test to Telegram API
    if not 'TELEGRAM' in config:
        print('[ERROR] The [TELEGRAM] section was not defined within conf.cfg. Ensure conf.cfg contents are correct.')
        sys.exit(0)

    try:
        telegram_api_id = config.get('TELEGRAM', 'api_id')
        telegram_api_hash = config.get('TELEGRAM', 'api_hash')
        telegram_session_name = config.get('TELEGRAM', 'session_name')
    except Exception as e:
        print('[ERROR] Check ../etc/conf.cfg to ensure the following variables have been set:\n')
        print('[TELEGRAM] api_id \n')
        print('[TELEGRAM] api_hash \n')
        print('[TELEGRAM] session_name \n')
        sys.exit(0)
    # /End Check Telegram configuration

except FileNotFoundError:
    print('[ERROR] ../etc/conf.cfg was not found. Copy conf.cfg.sample to conf.cfg and update its contents.')
    sys.exit(0)

# Asynchronous call to get messages from entity (i.e. Channel or User)
async def get_entity_messages(client, entity, min_id=0, max_id=0):
    try:
        await telegram.get_all_channel_messages(client, entity, pyail, min_id=min_id, max_id=max_id, feeder_uuid=feeder_uuid)
    except ValueError as e:
        print(f'Error: {e}')
        sys.exit(0)

if __name__ == '__main__':
    # # TODO: add DEBUG
    parser = argparse.ArgumentParser(description='AIL Telegram feeder')
    parser.add_argument('-e', '--entity', help='Get all messages from an entity: channel or User id', type=str,
                        dest='entity', default=None)
    parser.add_argument('--min', help='message min id', type=int, default=0, dest='mess_min_id')
    parser.add_argument('--max', help='message max id', type=int, default=0, dest='mess_max_id')

    parser.add_argument('--join', help='Join a public Channel', type=str, dest='channel_to_join', default=None)
    # parser.add_argument('--joinPrivate', help='Join a private Channel using a hash ID', type=str, dest='join_hash_id', default=None)
    parser.add_argument('--leave', help='Leave a Channel', type=str, dest='channel_to_leave', default=None)
    parser.add_argument('--checkId', help='Check if an invite ID is valid', type=str, dest='check_id', default=None)

    parser.add_argument('--channels', help='List all channels joined', action='store_true')
    parser.add_argument('--getall', help='Get all message from all joined channels', action='store_true')
    parser.add_argument('-v', '--verbose', help='Verbose output', action="store_true", default=False)

    args = parser.parse_args()
    # if args.verbose:
    #    parser.print_help()
    #    sys.exit(0)

    # # TODO: ADD Channel monitoring
    if not args.entity and not args.channel_to_join and not args.channel_to_leave and not args.check_id and not args.channels and not args.getall:
        parser.print_help()
        sys.exit(0)

    #### ENTITY ####
    entity = args.entity

    # sanityse entity
    entity = telegram.sanityse_entity(entity)

    # sanityse message min_id, max_id
    min_id = telegram.sanityse_message_id(args.mess_min_id)
    max_id = telegram.sanityse_message_id(args.mess_max_id)
    ##-- ENTITY --##

    #### CHANNEL ####
    channel_to_join = args.channel_to_join
    channel_to_leave = args.channel_to_leave
    check_id = args.check_id
    get_channels = args.channels
    get_all_messages = args.getall
    # join_hash_id = args.join_hash_id
    ##-- CHANNEL --##

    # start bot
    client = TelegramClient(telegram_session_name, telegram_api_id, telegram_api_hash)
    # connect client
    client.start()
    if not client.is_connected():
        print('connection error')

    with client:
        if channel_to_join:
            client.loop.run_until_complete(telegram.join_public_channel(client, channel_to_join))
        if channel_to_leave:
            client.loop.run_until_complete(telegram.leave_public_channel(client, channel_to_leave))
        if check_id:
            client.loop.run_until_complete(telegram.validate_join_code(client, check_id))
        # if join_hash_id:
        #    client.loop.run_until_complete(telegram.join_private_channel(client, join_hash_id))
        if args.channels is True:
            channels_joined = client.loop.run_until_complete(telegram.get_current_channels(client))
            print(channels_joined)
        if args.getall is True:
            channels_joined = client.loop.run_until_complete(telegram.get_current_channels(client))
            print(channels_joined)
            i = 0
            while i < len(channels_joined):
                print(channels_joined[i])
                entity = channels_joined[i]
                client.loop.run_until_complete(get_entity_messages(client, entity, min_id=min_id, max_id=max_id))
                i = i + 1
        if entity:
            client.loop.run_until_complete(get_entity_messages(client, entity, min_id=min_id, max_id=max_id))

        # res = client.loop.run_until_complete( telegram.get_channel_all_users(client, entity) )
        # print(res)
        # client.loop.run_until_complete( get_channel_admins(client, entity) )
