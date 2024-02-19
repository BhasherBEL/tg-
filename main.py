import tgtg
from tgtg import TgtgClient
from tgtg.exceptions import TgtgAPIError
import os
import json
import telegram
import asyncio
import time
import datetime
import requests
import random

###################################
#              UTILS              #
###################################

def get_env(name, default=None, mandatory=False):
    """Get an environment variable, with a default value and type casting."""
    content = os.environ.get(name, default)

    if mandatory and content is None:
        raise ValueError(f'Missing environment variable {name}')

    if type(default) == str:
        return content.lower() in ('true', '1')
    if type(default) == bool:
        return content
    if type(default) == int:
        return int(content)
    if type(default) == float:
        return float(content)
    return content
    
def parse_duration(seconds):
    """Parse a duration in seconds to a human readable format."""
    seconds = int(seconds)
    minutes = seconds // 60
    seconds = seconds % 60
    hours = minutes // 60
    minutes = minutes % 60

    if hours > 0:
        return f'{hours}h {minutes}m {seconds}s'
    elif minutes > 0:
        return f'{minutes}m {seconds}s'
    else:
        return f'{seconds}s'

def apply_randomness(value, randomness):
    """Apply randomness to a value."""
    return round(value + randomness * value * (2 * random.random() - 1))

####################################
#              CONFIG              #
####################################

TGTG_EMAIL = get_env('TGTG_EMAIL', mandatory=True)
TELEGRAM_NOTIFICATIONS = get_env('TELEGRAM_NOTIFICATIONS', False)
TELEGRAM_TOKEN = get_env('TELEGRAM_TOKEN', mandatory=TELEGRAM_NOTIFICATIONS)
TELEGRAM_ID = get_env('TELEGRAM_ID', mandatory=TELEGRAM_NOTIFICATIONS)
MATRIX_NOTIFICATIONS = get_env('MATRIX_NOTIFICATIONS', False)
MATRIX_URL = get_env('MATRIX_URL', mandatory=MATRIX_NOTIFICATIONS)
MATRIX_BASIC_AUTH_USER = get_env('MATRIX_BASIC_AUTH_USER', mandatory=MATRIX_NOTIFICATIONS)
MATRIX_BASIC_AUTH_PASS = get_env('MATRIX_BASIC_AUTH_PASS', mandatory=MATRIX_NOTIFICATIONS)

INITIAL_WAITING_TIME = get_env('INITIAL_WAITING_TIME', 60)
WAITING_TIME_LIMIT = get_env('WAITING_TIME_LIMIT', 60 * 60 * 24)
WAITING_TIME_INCREASE = get_env('WAITING_TIME_FACTOR', 2)
RANDOMNESS = get_env('RANDOMNESS', 0.1)
INTERVAL = get_env('INTERVAL', 60)

REMOVAL_NOTIFICATIONS = get_env('REMOVAL_NOTIFICATIONS', False)

# Reduce frequency of polling to avoid rate limiting
tgtg.POLLING_WAIT_TIME = get_env('LOGIN_POLLING_WAIT_TIME', 30)
tgtg.MAX_POLLING_TRIES = get_env('LOGIN_MAX_POLLING_TRIES', 10)

TOKEN_PATH = get_env('TOKEN_PATH', '/data/token')

####################################
#               MAIN               #
####################################

waiting_time = INITIAL_WAITING_TIME

tgtgClient = None
telegram_bot = telegram.Bot(TELEGRAM_TOKEN) if TELEGRAM_NOTIFICATIONS else None


async def send_message(text):
    if TELEGRAM_NOTIFICATIONS:
        async with telegram_bot:
            await telegram_bot.send_message(
                chat_id=TELEGRAM_ID,
                text='\n'.join(['Too good to Go'] + text)
            )
        
    if MATRIX_NOTIFICATIONS:
        requests.post(
            url=get_env('MATRIX_URL'),
            headers={
                'Content-Type': 'application/json',
            },
            auth=(MATRIX_BASIC_AUTH_USER, MATRIX_BASIC_AUTH_PASS),
            json={
            'title': 'Too Good to Go',
            'list': text,
        }
        )


def catch_api_error(e, message):
    global waiting_time

    print('ERROR: ', e)

    real_waiting_time = apply_randomness(waiting_time, RANDOMNESS)
    print(f'{message}, retrying in {parse_duration(real_waiting_time)}')

    time.sleep(real_waiting_time)

    waiting_time = min(waiting_time * WAITING_TIME_INCREASE, WAITING_TIME_LIMIT)


async def get_credentials():
    while True:
        try:
            await send_message(['Open the link to login to tgtg'])
            return tgtgClient.get_credentials()
        except TgtgAPIError as e:
            catch_api_error(e, 'tg² failed to get credentials')


async def load_creds():
    global tgtgClient, telegram_bot

    if not os.path.exists(TOKEN_PATH):
        tgtgClient = TgtgClient(email=TGTG_EMAIL)
        print('Waiting for credentials ...')
        credentials = await get_credentials()
        with open(TOKEN_PATH, 'w') as file:
            file.write(str(credentials))
        print('Credentials stored in file')
    else:
        with open(TOKEN_PATH, 'r') as file:
            credentials = json.loads(file.read().replace('\'', '"'))
        print('Credentials loaded from file')

    tgtgClient = TgtgClient(**credentials)


async def main():
    await load_creds()
    await send_message(['tg² telegram_bot is watching!'])

    last = []

    while True:
        try:
            items = tgtgClient.get_items()

            texts = []

            next = []

            for item in items:
                if item['items_available'] > 0:
                    next.append(item["item"]["item_id"])
                    if item["item"]["item_id"] not in last:
                        amount = item["items_available"]
                        item_name = item["item"]["name"]
                        price = item["item"]["price_including_taxes"]["minor_units"]/(10**item["item"]["price_including_taxes"]["decimals"])
                        store_name = item["store"]["store_name"]
                        store_branch = item["store"]["branch"]

                        name = ', '.join(filter(bool, [item_name, store_name, store_branch]))

                        if not name:
                            name = "Panier anti-gaspi"

                        texts.append(f'{amount} x "{name}" ({price:.2f}€)')
                elif REMOVAL_NOTIFICATIONS and item["item"]["item_id"] in last:
                        amount = item["items_available"]
                        name = item["item"]["name"]
                        price = item["item"]["price_including_taxes"]["minor_units"]/(10**item["item"]["price_including_taxes"]["decimals"])
                        store_name = item["store"]["store_name"]
                        store_branch = item["store"]["branch"]

                        name = ', '.join(filter(bool, [item_name, store_name, store_branch]))

                        if not name:
                            name = "Panier anti-gaspi"

                        texts.append(f'no more "{name}"')

            
            if len(texts) > 1:

                print(f'\n{datetime.datetime.now()}: {len(texts)-1} new items available')

                await send_message(texts)
            else:
                print('-', end='', flush=True)
            
            last = next
            real_interval = INTERVAL + RANDOMNESS * INTERVAL * (2 * random.random() - 1)
            time.sleep(INTERVAL)

            waiting_time = INITIAL_WAITING_TIME

        except TgtgAPIError as e:
            catch_api_error(e, 'tg² failed to get items')

if __name__ == '__main__':
    if not check_env():
        print('Missing environment variables')
        exit(1)

    asyncio.run(main())
