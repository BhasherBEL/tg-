import config

from tgtg import TgtgClient
import os
import json
import telegram
import asyncio
import time
import datetime


async def main():
    if not os.path.exists('token'):
        client = TgtgClient(email=config.email)
        credentials = client.get_credentials()
        with open('token', 'w') as file:
            file.write(str(credentials))
    else:
        with open('token', 'r') as file:
            credentials = json.loads(file.read().replace('\'', '"'))


    client = TgtgClient(**credentials)
    bot = telegram.Bot(config.telegram_token)

    async with bot:
        await bot.send_message(chat_id=config.telegram_id, text='tg² bot is watching!')

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
                    name = item["item"]["name"]
                    price = item["item"]["price_including_taxes"]["minor_units"]/(10**item["item"]["price_including_taxes"]["decimals"])
                    store = item["store"]["store_name"] + ' (' + item["store"]["branch"] + ')'

                    if not name:
                        name = "Panier anti-gaspi"

                    texts.append(f' - {amount} item(s) of "{name}" ({price:.2f}€) available at "{store}"')
            elif item["item"]["item_id"] in last:
                    amount = item["items_available"]
                    name = item["item"]["name"]
                    price = item["item"]["price_including_taxes"]["minor_units"]/(10**item["item"]["price_including_taxes"]["decimals"])
                    store = item["store"]["store_name"]

                    if not name:
                        name = "Panier anti-gaspi"

                    texts.append(f' - No more "{name}" ({price:.2f}€) available at "{store}"')

        
        if len(texts) > 1:

            print(f'\n{datetime.datetime.now()}: {len(texts)-1} new items available')

            async with bot:
                await bot.send_message(chat_id=config.telegram_id, text='\n'.join(texts))
        else:
            print('-', end='', flush=True)
        
        last = next
        time.sleep(60)

if __name__ == '__main__':
    asyncio.run(main())
