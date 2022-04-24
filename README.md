# ail-feeder-telegram
External telegram feeder for AIL framework (with an automated user account)

## Install

- Install python3 dependencies:
```bash
pip3 install -U -r requirements.txt
```

- Copy config file:
```bash
cp etc/conf.cfg.sample etc/conf.cfg
```

## Configuration

Add your telegram account in `etc/conf.cfg`:
  - Login in with your [telegram phone number](https://my.telegram.org/auth)
  - Click under API Development tools.
  - Create new application
  - Fill `App title` and `Short name` in your application details
  - Create application and retrieve your API ID and Hash
  - Add your API ID and Hash in `etc/conf.cfg`


 :warning: **Telegram API hash is secret and can't be revoked** :warning:  
You can use this API ID and hash with any phone number or even for bot accounts


## Usage

feeder.py
* --entity [Channel or User ID] (_Get all messages from an entity: channel or User id_)
* --min [int] (_message min id_)
* --max [int] (_message max id_)
* --join [Channel ID] (_Join a public Channel_)
* --leave [Channel ID] (_Leave a Channel_)
* --checkId [Invite ID] (_Check if an invite ID is valid_)
* --channels (_List all joined channel IDs_)
* --getall (_Get all messages from all joined channel IDs_)
* --verbose (_Not yet implemented_)

## Joining Channels
```bash
python3 bin/feeder.py --join CHANNEL_NAME 
```
Channels can also be joined from the mobile application on Apple or Android.
Once the script is re-run, the newly joined channel will be added to the messages queue.

## Leaving Channels
```bash
python3 bin/feeder.py --leave CHANNEL_NAME 
```
Channels can also be left from the mobile application on Apple or Android.
If you leave a channel whilst the script is running there will likely be an exception error.

## Get Joined Channels
```bash
python3 bin/feeder.py --channels 
```
Running this action will export a python list of channel IDs your Telegram account has joined.
There is not a whole lot of useful information in this list, however you can pass this list on to
another account to join the same accounts.

If you join too many channels, too quickly, you will experience a waiting period before you can join any more.

## Get ALL Messages from ALL Joined Channels
```bash
python3 bin/feeder.py --getall 
```
If you run in this action, and you have joined a lot of active channels
this will result in AIL-Framework's API being bombarded by lots of message outputs.
If you do this, be prepared for your system to max out it's CPU and RAM resources.
