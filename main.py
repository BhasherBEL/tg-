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


def get_env(name, default=None):
    content = os.environ.get(name, default)

    if type(default) == bool:
        return content.lower() in ('true', '1')
    if type(default) == int:
        return int(content)
    if type(default) == float:
        return float(content)
    return content


initial_waiting_time = get_env('INITIAL_WAITING_TIME', 60)
waiting_time = initial_waiting_time
waiting_time_limit = get_env('WAITING_TIME_LIMIT', 60 * 60 * 24)
waiting_time_increase = get_env('WAITING_TIME_FACTOR', 2)

randomness = get_env('RANDOMNESS', 0.1)

interval = get_env('INTERVAL', 60)

# Reduce frequency of polling to avoid rate limiting
tgtg.POLLING_WAIT_TIME = get_env('LOGIN_POLLING_WAIT_TIME', 30)
tgtg.MAX_POLLING_TRIES = get_env('LOGIN_MAX_POLLING_TRIES', 10)

client = None
telegram_bot = None
removal_notification = get_env('REMOVAL_NOTIFICATION', False)

TOKEN_PATH = get_env('TOKEN_PATH', '/data/token')

def parse_duration(seconds):
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


def check_env():
    if get_env('TGTG_EMAIL') is None:
        return False
    if get_env('TELEGRAM') is None and os.environ.get('MATRIX') is None:
        return False
    if get_env('TELEGRAM') is not None and (os.environ.get('TELEGRAM_TOKEN') is None or os.environ.get('TELEGRAM_ID') is None):
        return False
    if get_env('MATRIX') is not None and os.environ.get('MATRIX_URL') is None:
        return False
    return True

def retry_on_api_error(message):
    def decorator(func):
        def wrapper(*args, **kwargs):
            global waiting_time

            while True:
                try:
                    return func(*args, **kwargs)
                except TgtgAPIError as e:
                    print('ERROR: ', e)
                    real_waiting_time = round(waiting_time + randomness * waiting_time * (2 * random.random() - 1))
                    print(f'ls, retrying in {parse_duration(real_waiting_time)}')
                    time.sleep(real_waiting_time)

                    if waiting_time < waiting_time_limit:
                        waiting_time *= waiting_time_increase

        return wrapper
    return decorator

@retry_on_api_error('tg² failed to get credentials')
def get_credentials():
    return client.get_credentials()


def load_creds():
    global client, telegram_bot

    if not os.path.exists(TOKEN_PATH):
        client = TgtgClient(email=get_env('TGTG_EMAIL'))
        print('Waiting for credentials ...')
        credentials = get_credentials()
        with open(TOKEN_PATH, 'w') as file:
            file.write(str(credentials))
        print('Credentials stored in file')
    else:
        with open(TOKEN_PATH, 'r') as file:
            credentials = json.loads(file.read().replace('\'', '"'))
        print('Credentials loaded from file')

    client = TgtgClient(**credentials)
    if get_env('TELEGRAM').lower() == 'true':
        telegram_bot = telegram.Bot(os.environ['TELEGRAM_TOKEN'])


async def send_message(text):
    if get_env('TELEGRAM').lower() == 'true':
        async with telegram_bot:
            await telegram_bot.send_message(chat_id=get_env('TELEGRAM_ID'), text='\n'.join(['Too good to Go'] + text))
    if get_env('MATRIX').lower() == 'true':
        dic = {
            'title': 'Too Good to Go',
            'list': text,
        }

        response = requests.post(
            url=get_env('MATRIX_URL'),
            headers={
                'Content-Type': 'application/json',
            },
            auth=(get_env('MATRIX_BASIC_AUTH_USER'), os.environ.get('MATRIX_BASIC_AUTH_PASS')),
            json=dic
        )


async def main():
    await send_message(['tg² telegram_bot is watching!'])

    last = []

    while True:
        try:
            items = client.get_items()

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
                elif removal_notification and item["item"]["item_id"] in last:
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
            real_interval = interval + randomness * interval * (2 * random.random() - 1)
            time.sleep(interval)

            waiting_time = initial_waiting_time

        except TgtgAPIError as e:
            print(e)
            real_waiting_time = round(waiting_time + randomness * waiting_time * (2 * random.random() - 1))
            await send_message([f'tg² failed to fetch data, retrying in {parse_duration(real_waiting_time)}'])
            time.sleep(real_waiting_time)

            if waiting_time < waiting_time_limit:
                waiting_time *= waiting_time_increase

if __name__ == '__main__':
    if not check_env():
        print('Missing environment variables')
        exit(1)

    load_creds()
    asyncio.run(main())
