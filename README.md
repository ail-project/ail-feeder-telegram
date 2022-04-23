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
* --entity [Channel or User ID] (Get all messages from an entity: channel or User id)
* --min [int] (message min id)
* --max [int] (message max id)
* --join [Channel ID] (Join a public Channel)
* --leave [Channel ID] (Leave a Channel)
* --checkId [Invite ID] (Check if an invite ID is valid)
* --channels (List all joined channel IDs)
* --getall (Get all messages from all joined channel IDs)