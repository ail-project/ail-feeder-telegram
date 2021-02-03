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
