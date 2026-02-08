import asyncio
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message
import aiohttp

BOT_TOKEN = "bot api token"
ADMIN_ID = #yours telegram id  
TRACK_NUMBER = "yours track number"

YOUR_COOKIES = "cookie"

API_URL_TEMPLATE = "https://tracking.ozon.ru/p-api/ozon-track-bff/tracking/{track_number}"

STATUS_DETAILS = {
    "Created": {"title": "Cоздан", "desc": "Мы получили заказ, продавец уже собирает его"},
    "TransferringToDelivery": {"title": "Передается в доставку", "desc": "Продавец собрал заказ и передаёт его в доставку."},
    "WayToCity": {"title": "Заказ принят перевозчиком", "desc": "Он отвезёт заказ на таможню."},
    "ParcelDepartureFromCarrier": {"title": "Заказ везут на таможню в стране отправления", "desc": "Обычно это занимает до 10 дней."},
    "ArrivedToOutwardExchangeOffice": {"title": "Заказ привезли на таможню для экспортного оформления", "desc": ""},
    "OutFromOutwardExchangeOffice": {"title": "Заказ везут на таможню в стране назначения", "desc": "Он прошел экспортное оформление."},
    "ArrivedAtDestinationCountry": {"title": "Заказ привезли в страну назначения", "desc": "Его отвезут на таможенное оформление."},
    "CustomsClearanceStarted": {"title": "Заказ передан на импортное таможенное оформление", "desc": "Его готовят к оформлению."},
    "CustomsClearanceInProcess": {"title": "Заказ проходит импортное таможенное оформление", "desc": ""},
    "CustomsClearanceCompleted": {"title": "Заказ выпущен импортной таможней", "desc": "Его готовят к отправке на сортировочный терминал."},
    "SentToSortingCenter": {"title": "Заказ отправили на сортировочный терминал", "desc": "Его подготовят к доставке в город получателя."},
    "ReleasedFromSortingCenter": {"title": "Заказ покинул сортировочный терминал", "desc": "Его подготовили к доставке в город получателя."},
    "AwaitingRecipientCity": {"title": "Заказ ожидает отправки в город получателя", "desc": "Скорость отправки зависит от загруженности склада."},
    "InTransitRecipientCity": {"title": "Заказ везут в город получателя", "desc": "Его доставят в сортировочный центр."},
    "ParcelIsOnTheWay": {"title": "Заказ везут", "desc": "Мы сообщим, когда его доставят."},
    "FantomDelivery": {"title": "Заказ в работе", "desc": "Скоро его отправят дальше."},
    "AvailableForPickup": {"title": "Заказ в пункте выдачи", "desc": "Успейте забрать его в течение 14 дней."},
    "Received": {"title": "Заказ получен", "desc": "Доставка завершена."}
}

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

last_known_status_msg = {}

def format_date(date_string):
    if not date_string: return ""
    try:
        dt_object = datetime.fromisoformat(date_string.replace('Z', '+00:00'))
        return dt_object.strftime('%d.%m.%y, %H:%M')
    except:
        return date_string

async def get_ozon_data_message(track_number):
    api_url = API_URL_TEMPLATE.format(track_number=track_number)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:147.0) Gecko/20100101 Firefox/147.0",
        "Accept": "application/json, text/plain, */*",
        "X-O3-App-Name": "tpl-ui-ozon-track", "X-O3-App-Version": "release/TPLAPI-4899",
        "Cookie": YOUR_COOKIES, "Referer": f"https://tracking.ozon.ru/?track={track_number}",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, headers=headers) as resp:
                if resp.status != 200:
                    logging.error(f"Ошибка Ozon для {track_number}: {resp.status}")
                    if resp.status == 403: return "COOKIE_EXPIRED"
                    return None
                
                data = await resp.json()

                title, description, event_time, event_key = "Статус не определен", "", "", ""
                
                if "items" in data and data["items"]:
                    last_event = data["items"][-1]
                    event_key = last_event.get("event", "UnknownEvent")
                    status_info = STATUS_DETAILS.get(event_key)
                    
                    title = status_info["title"] if status_info else event_key
                    description = status_info.get("desc", "") if status_info else ""
                    event_time = format_date(last_event.get("moment"))

                delivery_begin = format_date(data.get("deliveryDateBegin")).split(',')[0]
                delivery_end = format_date(data.get("deliveryDateEnd")).split(',')[0]
                
                emoji = "<tg-emoji emoji-id='5206607081334906820'>✔️</tg-emoji>" if event_key == "Received" else "<tg-emoji emoji-id='5298487770510020895'>💤</tg-emoji>"
                msg = f"{emoji} <b>{title}</b>\n"
                if event_time: msg += f"<i>({event_time})</i>\n\n"
                if description: msg += f"<tg-emoji emoji-id='5472012979073456920'>🔁</tg-emoji> {description}\n\n"
                if event_key != "Received":
                    msg += f"<tg-emoji emoji-id='5206270085315961515'>🍔</tg-emoji> <b>Ожидаемая дата доставки:</b>\nс {delivery_begin} до {delivery_end}"
                
                return msg

    except Exception as e:
        logging.error(f"Сбой скрипта для {track_number}: {e}")
        return None

async def monitor_task():
    global last_known_status_msg
    text = await get_ozon_data_message(TRACK_NUMBER)
    if text and text != "COOKIE_EXPIRED":
        last_known_status_msg[TRACK_NUMBER] = text
        await bot.send_message(ADMIN_ID, f"<tg-emoji emoji-id='5206607081334906820'>✔️</tg-emoji> Бот запущен! Слежу за посылкой:\n\n{text}", parse_mode="HTML")

    while True:
        await asyncio.sleep(3600)
        
        current_status = await get_ozon_data_message(TRACK_NUMBER)
        
        if current_status == "COOKIE_EXPIRED":
            await bot.send_message(ADMIN_ID, "<tg-emoji emoji-id='5447644880824181073'>⚠️</tg-emoji><b> Куки устарели!</b>\nБот не может проверить статус.", parse_mode="HTML")
            await asyncio.sleep(86400)
            continue

        if current_status and current_status != last_known_status_msg.get(TRACK_NUMBER):
            last_known_status_msg[TRACK_NUMBER] = current_status
            await bot.send_message(ADMIN_ID, f"<tg-emoji emoji-id='5256103272296499934'>🍿</tg-emoji> <b>Обновление!</b>\n\n{current_status}", parse_mode="HTML")

@dp.message(Command("start", "status"))
async def check_status_command(msg: Message):
    if msg.from_user.id != ADMIN_ID: return
    
    await msg.answer("<tg-emoji emoji-id='5443132326189996902'>🧑‍💻</tg-emoji> Проверяю...", parse_mode="HTML")
    text = await get_ozon_data_message(TRACK_NUMBER)

    if text == "COOKIE_EXPIRED":
        await msg.answer("<tg-emoji emoji-id='5210952531676504517'>❌</tg-emoji><b> Ошибка: Куки устарели.</b>", parse_mode="HTML")
    elif text:
        last_known_status_msg[TRACK_NUMBER] = text
        await msg.answer(text, parse_mode="HTML")
    else:
        await msg.answer("Не удалось получить данные.")

if __name__ == "__main__":
    asyncio.run(dp.start_polling(bot))