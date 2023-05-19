from tgtg import TgtgClient
import os
import json
import telegram
import asyncio
import time
import datetime


client = None
bot = None


def check_env():
    return not (os.environ.get('TGTG_EMAIL') is None or os.environ.get('TELEGRAM_TOKEN') is None or os.environ.get('TELEGRAM_ID') is None)


def load_creds():
    global client, bot

    if not os.path.exists('/data/token'):
        client = TgtgClient(email=os.environ.get('TGTG_EMAIL'))
        credentials = client.get_credentials()
        with open('/data/token', 'w') as file:
            file.write(str(credentials))
    else:
        with open('/data/token', 'r') as file:
            credentials = json.loads(file.read().replace('\'', '"'))

    client = TgtgClient(**credentials)
    bot = telegram.Bot(os.environ['TELEGRAM_TOKEN'])


async def send_message(text):
    async with bot:
        await bot.send_message(chat_id=os.environ.get('TELEGRAM_ID'), text=text)


async def main():
    await send_message('tg² bot is watching!')

    last = []

    while True:
        items = client.get_items()

        texts = ['Too good to go']

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

                    texts.append(f'{amount} x "{name}" ({price:.2f}€)')
            # elif item["item"]["item_id"] in last:
            #         amount = item["items_available"]
            #         name = item["item"]["name"]
            #         price = item["item"]["price_including_taxes"]["minor_units"]/(10**item["item"]["price_including_taxes"]["decimals"])
            #         store = item["store"]["store_name"]

            #         if not name:
            #             name = "Panier anti-gaspi"

            #         texts.append(f' - No more "{name}" ({price:.2f}€) available at "{store}"')

        
        if len(texts) > 1:

            print(f'\n{datetime.datetime.now()}: {len(texts)-1} new items available')

            await send_message('\n'.join(texts))
        else:
            print('-', end='', flush=True)
        
        last = next
        time.sleep(60)

if __name__ == '__main__':
    check_env()
    load_creds()
    asyncio.run(main())
