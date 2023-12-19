from tgtg import TgtgClient
import os
import json
import telegram
import asyncio
import time
import datetime
import requests


client = None
telegram_bot = None
removal_notification = os.environ.get('REMOVAL_NOTIFICATION')

if removal_notification is None:
    removal_notification = False


def check_env():
    if os.environ.get('TGTG_EMAIL') is None:
        return False
    if os.environ.get('TELEGRAM') is None and os.environ.get('MATRIX') is None:
        return False
    if os.environ.get('TELEGRAM') is not None and (os.environ.get('TELEGRAM_TOKEN') is None or os.environ.get('TELEGRAM_ID') is None):
        return False
    if os.environ.get('MATRIX') is not None and os.environ.get('MATRIX_URL') is None:
        return False
    return True


def load_creds():
    global client, telegram_bot

    if not os.path.exists('/data/token'):
        client = TgtgClient(email=os.environ.get('TGTG_EMAIL'))
        print('Waiting for credentials ...')
        credentials = client.get_credentials()
        with open('/data/token', 'w') as file:
            file.write(str(credentials))
        print('Credentials stored in file')
    else:
        with open('/data/token', 'r') as file:
            credentials = json.loads(file.read().replace('\'', '"'))
        print('Credentials loaded from file')

    client = TgtgClient(**credentials)
    if os.environ.get('TELEGRAM') is not None:
        telegram_bot = telegram.Bot(os.environ['TELEGRAM_TOKEN'])


async def send_message(text):
    if os.environ.get('TELEGRAM') is not None:
        async with telegram_bot:
            await telegram_bot.send_message(chat_id=os.environ.get('TELEGRAM_ID'), text='\n'.join(['Too good to Go'] + text))
    if os.environ.get('MATRIX') is not None:
        dic = {
            'title': 'Too Good to Go',
            'list': text,
        }

        response = requests.post(
            url=os.environ.get('MATRIX_URL'),
            headers={
                'Content-Type': 'application/json',
            },
            auth=(os.environ.get('MATRIX_BASIC_AUTH_USER'), os.environ.get('MATRIX_BASIC_AUTH_PASS')),
            json=dic
        )


async def main():
    await send_message(['tg² telegram_bot is watching!'])

    last = []

    while True:
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
        time.sleep(60)

if __name__ == '__main__':
    print('Check environ:', check_env())
    load_creds()
    asyncio.run(main())
