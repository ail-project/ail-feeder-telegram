#!/usr/bin/env python3
# -*-coding:UTF-8 -*

import argparse
import configparser
import json
import sys
import os
# import time

from telegram import TGFeeder
from pyail import PyAIL

dir_path = os.path.dirname(os.path.realpath(__file__))
default_config_file = os.path.join(dir_path, '../etc/conf.cfg')

# TODO logs

def load_config_file(config_path):
    try:
        config = configparser.ConfigParser()
        config.read(config_path)
    except FileNotFoundError:
        print(f'[ERROR] {config_path} was not found. Copy conf.cfg.sample to conf.cfg and update its contents.')
        sys.exit(0)
    except Exception as e:
        print(f'Error opening config file: {e}')
        sys.exit(0)

    # Check AIL configuration, set variables and do the connection test to AIL API
    if 'AIL' not in config:
        print('[ERROR] The [AIL] section was not defined within conf.cfg. Ensure conf.cfg contents are correct.')
        sys.exit(0)

    conf = {}
    ail_clients = []
    ail_conf = {}

    try:
        # Set variables required for the Telegram Feeder
        conf['feeder_uuid'] = config.get('AIL', 'feeder_uuid')
        ail_feeder = config.getboolean('AIL', 'ail_feeder')

        if config.has_option('AIL', 'url'):
            ail_url = config.get('AIL', 'url')
            ail_key = config.get('AIL', 'apikey')
            ail_verifycert = config.getboolean('AIL', 'verifycert')
            ail_conf[ail_url] = {'key': ail_key, 'verifycert': ail_verifycert}

        for i in range(2, 11):
            if config.has_option('AIL', f'url{i}'):
                ail_url = config.get('AIL', f'url{i}')
                ail_key = config.get('AIL', f'apikey{i}')
                ail_verifycert = config.getboolean('AIL', f'verifycert{i}')
                ail_conf[ail_url] = {'key': ail_key, 'verifycert': ail_verifycert}
            else:
                break
    except Exception as e:
        print(e)
        print('[ERROR] Check ../etc/conf.cfg to ensure the following variables have been set:')
        print('    [AIL] feeder_uuid')
        print('    [AIL] url')
        print('    [AIL] apikey')
        sys.exit(0)

    if ail_feeder:
        for url in ail_conf:
            try:
                ail = PyAIL(url, ail_conf[url]['key'], ssl=ail_conf[url]['verifycert'])
            except Exception as e:
                print(e)
                print('[ERROR] Unable to connect to AIL Framework API. Please check [AIL] url, apikey and verifycert in ../etc/conf.cfg.\n')
                sys.exit(0)
            ail_clients.append(ail)
        conf['ail'] = ail_clients
    else:
        # print('[INFO] AIL Feeder has not been enabled in [AIL] ail_feeder. Feeder script will not send output to AIL.\n')
        conf['ail'] = None

    # EXECUTABLES CMD PATH
    try:
        conf['qpdf_cmd'] = config.get('EXECUTABLES', 'qpdf_cmd')
        conf['ghostscript_cmd'] = config.get('EXECUTABLES', 'ghostscript_cmd')

    except Exception as e:
        if str(e) == "No section: 'EXECUTABLES'":
            conf['qpdf_cmd'] = 'qpdf'
            conf['ghostscript_cmd'] = 'gs'
        else:
            print(e)
            print('[ERROR] Check ../etc/conf.cfg to ensure executables path are configured')
            print('    [EXECUTABLES] qpdf_cmd')
            print('    [EXECUTABLES] ghostscript_cmd')
            sys.exit(0)

    # Check Telegram configuration, set variables and do the connection test to Telegram API
    if 'TELEGRAM' not in config:
        print('[ERROR] The [TELEGRAM] section was not defined within conf.cfg. Ensure conf.cfg contents are correct.')
        sys.exit(0)

    try:
        conf['telegram'] = {}
        conf['telegram']['id'] = int(config.get('TELEGRAM', 'api_id'))
        conf['telegram']['hash'] = config.get('TELEGRAM', 'api_hash')
        conf['telegram']['session_name'] = os.path.basename(config.get('TELEGRAM', 'session_name'))

        conf['extract_mentions'] = config.getboolean('TELEGRAM', 'extract_mentions')
    except Exception as e:
        print(e)
        print('[ERROR] Check ../etc/conf.cfg to ensure the following variables have been set:')
        print('    [TELEGRAM] api_id')
        print('    [TELEGRAM] api_hash')
        print('    [TELEGRAM] session_name')
        print('    [TELEGRAM] extract_mentions')
        sys.exit(0)
    try:
        conf['max_size_pdf'] = config.getint('TELEGRAM', 'max_size_pdf')
    except Exception:
        conf['max_size_pdf'] = 20000000

    return conf


def _create_messages_subparser(subparser):
    subparser.add_argument('--replies', action='store_true', help='Get replies')
    subparser.add_argument('--media', action='store_true', help='Download medias')  # TODO Limit size
    subparser.add_argument('--size_limit', type=int, help='Size limit for downloading medias')
    subparser.add_argument('--save_dir', help='Directory to save downloaded medias')
    subparser.add_argument('--mark_as_read', action='store_true', help='Mark messages as read')

def _json_print(mess):
    print(json.dumps(mess, indent=4, sort_keys=True))


if __name__ == '__main__':

    # parent
    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument('-c', '--config', type=str, help='Config File', default=argparse.SUPPRESS)

    parser = argparse.ArgumentParser(description='Telegram feeder', parents=[parent_parser])

    subparsers = parser.add_subparsers(dest='command')

    list_chats_parser = subparsers.add_parser('chats', help='List all joined chats', parents=[parent_parser])

    join_chat_parser = subparsers.add_parser('join', help='Join a chat by its id, username or with a hash invite', parents=[parent_parser])
    join_chat_parser.add_argument('-n', '--name', type=str, help='Id, hash or username of the chat to join')
    join_chat_parser.add_argument('-i', '--invite', type=str, help='Invite hash of the chat to join')

    get_chat_users_parser = subparsers.add_parser('leave', help='Leave a chat', parents=[parent_parser])
    get_chat_users_parser.add_argument('chat_id', help='ID, hash or username of the chat to leave')

    get_chat_users_parser = subparsers.add_parser('check', help='Check a chat/invite hash without joining', parents=[parent_parser])
    get_chat_users_parser.add_argument('invite', help='invite hash to check')

    messages_parser = subparsers.add_parser('messages', help='Get all messages from a chat', parents=[parent_parser])
    messages_parser.add_argument('chat_id', nargs='+', help='ID of the chat.')  # TODO NB messages
    messages_parser.add_argument('--min_id', type=int, help='minimal ID of chat messages.')
    messages_parser.add_argument('--max_id', type=int, help='maximum ID of chat messages.')
    _create_messages_subparser(messages_parser)

    message_parser = subparsers.add_parser('message', help='Get a message from a chat', parents=[parent_parser])
    message_parser.add_argument('chat_id', help='ID of the chat.')
    message_parser.add_argument('mess_id', help='ID of the message.')
    _create_messages_subparser(message_parser)

    monitor_chats_parser = subparsers.add_parser('monitor', help='Monitor chats', parents=[parent_parser])
    _create_messages_subparser(monitor_chats_parser)

    get_unread_parser = subparsers.add_parser('unread', help='Get all unread messages from all chats', parents=[parent_parser])
    _create_messages_subparser(get_unread_parser)

    # monitor_chats_parser.add_argument('chat_ids', nargs='+', help='IDs of chats to monitor')

    # return meta if no flags
    get_chat_users_parser = subparsers.add_parser('chat', help='Get a chat metadata, list of users, ...', parents=[parent_parser])
    get_chat_users_parser.add_argument('chat_id', help='ID, hash or username of the chat')
    get_chat_users_parser.add_argument('--users', action='store_true', help='Get a list of all the users of a chat')
    get_chat_users_parser.add_argument('--admins', action='store_true', help='Get a list of all the admin users of a chat')
    get_chat_users_parser.add_argument('--similar', action='store_true', help='Get a list of similar/recommended chats')
    # join ? leave ? shortcut

    get_metas_parser = subparsers.add_parser('entity', help='Get chat or user metadata', parents=[parent_parser])
    get_metas_parser.add_argument('entity_name', help='ID, hash or username of the chat/user')

    search_parser = subparsers.add_parser('search', help='Search for chats/users', parents=[parent_parser])
    search_parser.add_argument('to_search', help='String to search')

    args = parser.parse_args()

    # load config file
    if not hasattr(args, 'config'):
        cf = load_config_file(default_config_file)
    else:
        cf = load_config_file(args.config)

    # Start client
    tg = TGFeeder(cf['telegram']['id'], cf['telegram']['hash'], cf['telegram']['session_name'], ail_clients=cf['ail'],
                  extract_mentions=cf['extract_mentions'], qpdf_cmd=cf['qpdf_cmd'], ghostscript_cmd=cf['ghostscript_cmd'])
    tg.set_max_size(pdf=cf['max_size_pdf'])
    # Connect client
    tg.connect()

    # get loop
    loop = tg.loop
    # loop.run_until_complete(tg.client.get_dialogs())
    # Call the corresponding function based on the command
    if args.command == 'monitor':
        if args.media:
            download = True
        else:
            download = False
        if args.save_dir:
            save_dir = args.save_dir
        else:
            save_dir = ''
        loop.run_until_complete(tg.monitor_chats(download=download, save_dir=save_dir))
        tg.client.run_until_disconnected()
    else:
        if args.command == 'chats':
            r = loop.run_until_complete(tg.get_chats())
            _json_print(r)
            tg.client.disconnect()
        elif args.command == 'join':
            if not args.name and not args.invite:
                join_chat_parser.print_help()
                sys.exit(0)
            if args.name:
                chat = args.name
            else:
                chat = None
            if args.invite:
                invite = args.invite
            else:
                invite = None
            r = loop.run_until_complete(tg.join_chat(chat=chat, invite=invite))
            _json_print(r)
            tg.client.disconnect()
        elif args.command == 'leave':
            chat = args.chat_id
            r = loop.run_until_complete(tg.leave_chat(chat=chat))
            _json_print(r)
            tg.client.disconnect()
        elif args.command == 'check':
            invite = args.invite
            r = loop.run_until_complete(tg.check_invite(invite))
            _json_print(r)
            tg.client.disconnect()
        elif args.command == 'messages':
            chats = args.chat_id
            if args.replies:
                replies = True
            else:
                replies = False
            if args.mark_as_read:
                mark_read = True
            else:
                mark_read = False
            if args.media:
                download = True
            else:
                download = False
            if args.save_dir:
                save_dir = args.save_dir
            else:
                save_dir = ''

            # MIN/MAX Message ID
            if args.min_id or args.max_id:
                # MIN/MAX Message ID
                if args.min_id:
                    min_id = args.min_id
                    if min_id <= 0:
                        min_id = 0
                    else:
                        min_id = min_id - 1
                else:
                    min_id = 0

                if args.max_id:
                    max_id = args.max_id
                    if max_id <= 0:
                        max_id = 0
                    else:
                        max_id = max_id + 1
                else:
                    max_id = 0

                for chat in chats:
                    try:
                        loop.run_until_complete(tg.get_chat_messages(chat, download=download, save_dir=save_dir, replies=replies, mark_read=mark_read, min_id=min_id, max_id=max_id))
                    except:
                        tg.client.disconnect()
            else:
                for chat in chats:
                    # print('---------------')
                    # print('Extract Messages from:', chat)
                    try:
                        loop.run_until_complete(tg.get_chat_messages(chat, download=download, save_dir=save_dir, replies=replies, mark_read=mark_read))
                    except:
                        tg.client.disconnect()

        elif args.command == 'message':
            chat = args.chat_id
            mess_id = args.mess_id
            try:
                mess_id = int(mess_id)
            except ValueError:
                print('Invalid message ID')
                sys.exit(0)
            if mess_id <= 0:
                print('Fetching all messages')
                min_id = 0
                max_id = 0
            else:
                min_id = mess_id - 1
                max_id = mess_id + 1

            if args.replies:
                replies = True
            else:
                replies = False
            if args.mark_as_read:
                mark_read = True
            else:
                mark_read = False
            if args.media:
                download = True
            else:
                download = False
            if args.save_dir:
                save_dir = args.save_dir
            else:
                save_dir = ''
            try:
                loop.run_until_complete(tg.get_chat_messages(chat, min_id=min_id, max_id=max_id, download=download, save_dir=save_dir, replies=replies, mark_read=mark_read))
            except:
                tg.client.disconnect()

        elif args.command == 'unread':
            if args.replies:
                replies = True
            else:
                replies = False
            if args.media:
                download = True
            else:
                download = False
            if args.save_dir:
                save_dir = args.save_dir
            else:
                save_dir = ''
            loop.run_until_complete(tg.get_unread_message(download=download, save_dir=save_dir, replies=replies))
            tg.client.disconnect()
        elif args.command == 'chat':
            chat = args.chat_id
            if args.similar:
                similar = True
            else:
                similar = False
            if args.users or args.admins:
                if args.admins:
                    admin = True
                else:
                    admin = False
                r = loop.run_until_complete(tg.get_chat_users(chat, admin=admin))
                if r:
                    _json_print(r)
                tg.client.disconnect()
            else:
                r = loop.run_until_complete(tg.get_entity(chat, similar=similar, full=True))
                _json_print(r)
                tg.client.disconnect()
        elif args.command == 'entity':
            entity = args.entity_name
            r = loop.run_until_complete(tg.get_entity(entity))
            _json_print(r)
            tg.client.disconnect()
        elif args.command == 'search':
            to_search = args.to_search
            r = loop.run_until_complete(tg.search_contact(to_search))
            _json_print(r)
            tg.client.disconnect()
        else:
            parser.print_help()
