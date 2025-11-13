# ail-feeder-telegram
External telegram feeder for AIL framework (with an automated user account)

- [x] Forum channels
- [x] Replies Threads
- [x] Images Download
- [x] Users + channels meta and profile picture
- [x] Files download (Saved on disk)

## Install

```bash
sudo apt-get install cryptg libmagic1 ghostscript exiftool qpdf
```

- Install python3 dependencies:
```bash
pip3 install -U -r requirements.txt
```

- Copy config file:
```bash
cp etc/conf.cfg.sample etc/conf.cfg
```

## Configuration

### Telegram

Add your telegram account in `etc/conf.cfg`:
  - Login in with your [telegram phone number](https://my.telegram.org/auth)
  - Click under API Development tools.
  - Create new application
  - Fill `App title` and `Short name` in your application details
  - Create application and retrieve your API ID and Hash
  - Add your API ID and Hash in `etc/conf.cfg`


 :warning: **Telegram API hash is secret and can't be revoked** :warning:  
You can use this API ID and hash with any phone number or even for bot accounts

### AIL

- Add your AIL **URL** and **API key** in `etc/conf.cfg` to push messages to AIL
- Sending Message to AIL is optional

## Usage

feeder.py
* chats ( List all joined chats_ )
* join ( _Join a chat by its name or invite hash_ )
  * --name [Chat name] ( _chat name/username_ )
  * --invite [Invite Hash] ( _chat invite hash_ )
* leave [Channel] ( _Leave a Chat_ )
* check [Invite Hash] ( _Check an invite hash/chat without joining_ )
* messages [Chat ID/username] ( _Get all messages from a chat_ )
  * --min_id [Message ID] ( _Filter: Message Minimal ID_ )
  * --max_id [Message ID] ( _Filter: Message Maximum ID_ )
  * --replies ( _Get replies_ )
  * --mark_as_read ( _Mark messages as read_ )
  * --media ( _Download medias_ )
  * --save_dir ( _Directory to save downloaded medias_ )
* message [Chat ID/username] [Message ID] ( _Get a message from a chat_ )
  * --replies ( _Get replies_ )
  * --mark_as_read ( _Mark message as read_ )
  * --media ( _Download medias_ )
  * --save_dir ( _Directory to save downloaded medias_ )
* monitor ( _Monitor all joined chats_ )
* unread ( _Get all unread messages from all chats and mark them as read_ )
* chat [Chat ID/username] (  _Get a chat metadata, list of users/admins, ..._ )
  * --users ( _Get a list of all the users of a chat_ )
  * --admins ( _Get a list of all the admin users of a chat_ )
  * --similar ( _Get a list of similar/recommended chats_ )
* entity [Entity ID/username] ( _Get chat or user metadata_ )
* search [to_search] ( _Search for public Chats/Users_ )

## Joining Channels
```bash
python3 bin/feeder.py join -n CHANNEL_USERNAME 
```
```bash
python3 bin/feeder.py join -i INVITE_HASH 
```
Channels can also be joined from the mobile application on Apple or Android.
Once the script is re-run, the newly joined channel will be added to the messages queue.

## Leaving Channels
```bash
python3 bin/feeder.py leave CHANNEL_USERNAME/CHANNEL_ID 
```
Channels can also be left from the mobile application on Apple or Android.
If you leave a channel whilst the script is running there will likely be an exception error.

## Get all Channels
```bash
python3 bin/feeder.py chats 
```
Running this action will export a python list of channel IDs your Telegram account has joined.

If you join too many channels, too quickly, you might experience a waiting period before you can join a new one.

## Get Channel Messages
```bash
python3 bin/feeder.py messages CHANNEL_USERNAME/CHANNEL_ID
```

## MONITOR Messages from all Joined Channels
```bash
python3 bin/feeder.py monitor
```
