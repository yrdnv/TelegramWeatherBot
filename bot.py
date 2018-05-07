import datetime
import requests
import config
from aiogram import Bot, types
from aiogram.dispatcher import Dispatcher
from aiogram.utils import executor
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from sqlalchemy.exc import SQLAlchemyError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from db import Database, User


bot = Bot(token=config.token)
dp = Dispatcher(bot)


def request_weather(lat, lon):
    """
    This function make request to the openweathermap API.
    Return fully ready string that can be sent to user
    """
    try:
        r = requests.get('http://api.openweathermap.org/data/2.5/weather?lang=ru&units=metric&'
                     'lat=' + lat + '&lon=' + lon + '&APPID=' + config.weather_appid)
    except requests.RequestException:
        return 'Try again later'
    weather_response = r.json()

    city = weather_response['name']
    description = weather_response['weather'][0]['description']
    current_temp = weather_response['main']['temp']
    pressure = str(weather_response['main']['pressure'])  # давление
    humidity = str(weather_response['main']['humidity'])  # влажность
    wind = str(weather_response['wind']['speed'])  # скорость ветра м/с

    weather_message = "*{}*\n_{}_\n*Temp:* _{}_\n*Давление:* _{}_\n*Влажность:* _{}_\n*Ветер:* _{} м/с_\n".format\
        (city, description.capitalize(), current_temp, pressure, humidity, wind)

    return weather_message


def request_weather_tmrw(lat, lon):
    """
    This function return weather for tomorrow
    """
    today = datetime.date.today()
    tomorrow = today + datetime.timedelta(days=1)
    weather_messages = []
    try:
        r = requests.get('http://api.openweathermap.org/data/2.5/forecast?lang=ru&units=metric&'
                     'lat=' + lat + '&lon=' + lon + '&APPID=' + config.weather_appid)
    except requests.RequestException:
        return ['Try again later']

    weather_response = r.json()
    city = weather_response['city']['name']
    tomorrow_weather = [x for x in weather_response['list'] if str(tomorrow) in x['dt_txt']]
    for each in tomorrow_weather:
        date = each['dt_txt']
        description = each['weather'][0]['description']
        current_temp = each['main']['temp']
        pressure = str(each['main']['pressure'])  # давление
        humidity = str(each['main']['humidity'])  # влажность
        wind = str(each['wind']['speed'])  # скорость ветра м/с

        res = "*{}*\n_{}_\n*Temp:* _{}_\n*Давление:* _{}_\n*Влажность:* _{}_\n*Ветер:* _{} м/с_\n".format\
            (date, description.capitalize(), current_temp, pressure, humidity, wind)
        weather_messages.append(res)
    return weather_messages




@dp.message_handler(commands=['start']) #/start
async def start_process(msg):

    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    geo_button = types.KeyboardButton(text='Отправить местоположение', request_location=True)
    keyboard.add(geo_button)
    await bot.send_message(msg.chat.id, 'Окей! Мне потребуются твои координаты, для прогноза погоды.',
                           reply_markup=keyboard)



@dp.message_handler(content_types=['location'])
async def geo(msg):

    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton(text='Оформить подписку', callback_data='set'))
    keyboard.add(types.InlineKeyboardButton(text='Прогноз на завтра', callback_data='tomorrow'))
    lat = str(msg.location.latitude)
    lon = str(msg.location.longitude)
    # trying get and check last_update record in database for current user.
    # If record does not available in database we create new user
    try:
        database = Database()
        data = database.get_data(msg.chat.id)
        now = datetime.datetime.now()
        last_update = data.last_update
        next_update = data.last_update + datetime.timedelta(hours=1)

        if now > next_update:
            # if last update were more than one hour
            # we make new request to the API and save it in DB

            weather_message = request_weather(lat, lon)
            data.lat = lat
            data.lon = lon
            data.weather = weather_message
            data.last_update = datetime.datetime.now()
            database.session.commit()
            await bot.send_message(msg.chat.id, weather_message, reply_markup=keyboard, parse_mode='markdown')

        elif now < next_update:
            await bot.send_message(msg.chat.id,
                                   'Слишком много обращений, попробуйте позже\n'
                                   'Последнее обновление: {}\n'
                                   '{}\n /set - настройки'.format(data.last_update, data.weather), parse_mode='markdown')

    except SQLAlchemyError:
        # if current user not in DB
        weather_message = request_weather(lat, lon)
        database.add_user(msg.chat.username, msg.chat.id, lat, lon, weather_message, datetime.datetime.now())
        await bot.send_message(msg.chat.id, weather_message, reply_markup=keyboard, parse_mode='markdown')

    finally:
        database.session.close()


@dp.message_handler(commands=['set'])  #settings
async def set_subscribe(msg):

    try:
        database = Database()
        data = database.get_data(msg.chat.id)
        city = data.weather.split('\n')[0]
        keyboard = types.InlineKeyboardMarkup()
        button_1h = types.InlineKeyboardButton('Каждый час', callback_data='1')
        button_3h = types.InlineKeyboardButton('Каждые 3 часа', callback_data='3')
        button_6h = types.InlineKeyboardButton('Каждые 6 часов', callback_data='6')
        keyboard.add(*[button_1h, button_3h, button_6h])
        keyboard.insert(types.InlineKeyboardButton('Сменить локацию', callback_data='start'))
        keyboard.insert(types.InlineKeyboardButton('Отписаться от рассылки', callback_data='unset'))
        keyboard.add(types.InlineKeyboardButton('Текущий прогноз', callback_data='now'))
        keyboard.add(types.InlineKeyboardButton('Прогноз на завтра', callback_data='tomorrow'))
        await bot.send_message(msg.chat.id, 'Подписка для {}\n Сообщения будут приходить только днем'
                               .format(city), reply_markup=keyboard, parse_mode='markdown')


    except SQLAlchemyError:
        # user can't call settings if he doesn't get weather before
        await bot.send_message(msg.chat.id, 'Для начала получите погоду /start')
    finally:
        database.session.close()




@dp.callback_query_handler(func = lambda c: True) #callback processing
async def inline(callback):

    if callback.data == 'set':
        await set_subscribe(callback.message)

    elif callback.data == 'now':
        try:
            database = Database()
            data = database.get_data(callback.message.chat.id)
            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(types.InlineKeyboardButton(text='Оформить подписку', callback_data='set'))
            keyboard.add(types.InlineKeyboardButton(text='Прогноз на завтра', callback_data='tomorrow'))
            now = datetime.datetime.now()
            last_update = data.last_update
            next_update = data.last_update + datetime.timedelta(hours=1)
            if now > next_update:
            # if last update were more than one hour
            # we make new request to the API and save it in DB

                weather_message = request_weather(data.lat, data.lon)
                data.weather = weather_message
                data.last_update = datetime.datetime.now()
                database.session.commit()
                await bot.send_message(callback.message.chat.id, weather_message,
                                       reply_markup=keyboard, parse_mode='markdown')

            elif now < next_update:
                await bot.send_message(callback.message.chat.id,
                                       'Слишком много обращений, попробуйте позже\n'
                                       'Последнее обновление: {}\n'
                                       '{}\n /set - настройки'.
                                       format(data.last_update, data.weather), parse_mode='markdown')


        except SQLAlchemyError as e:
            pass
        finally:
            database.session.close()


    elif callback.data == 'start':
        await bot.edit_message_text('Меняем локацию...', callback.message.chat.id, callback.message.message_id)
        await start_process(callback.message)

    elif callback.data == 'unset':
        try:
            database = Database()
            data = database.get_data(callback.message.chat.id)
            data.subscribe = False
            data.period = 0
            database.session.commit()
            database.session.close()
            await bot.send_message(callback.message.chat.id, 'Вы успешно отписались от рассылки')
        except SQLAlchemyError as e:
            pass
        finally:
            database.session.close()

    elif callback.data == 'tomorrow':
        try:
            database = Database()
            data = database.get_data(callback.message.chat.id)
            city = data.weather.split('\n')[0]
            messages = request_weather_tmrw(data.lat, data.lon)
            await bot.send_message(data.chat_id, 'Погода на завтра {}'.format(city), parse_mode='markdown')
            for each in messages:
                await bot.send_message(data.chat_id, each, parse_mode='markdown')
            await bot.send_message(callback.message.chat.id, '/set - настройки')
        except SQLAlchemyError as e:
            pass
        finally:
            database.session.close()

    else:
        try:
            database = Database()
            data = database.get_data(callback.message.chat.id)
            data.subscribe = True
            data.period = int(callback.data)
            database.session.commit()
            await bot.edit_message_text('Вы выбрали {} час(a)\n'
                                        'Для смены локации /start\n'
                                        'Для управления подпиской /set'.format(callback.data),
                                        callback.message.chat.id, callback.message.message_id)
        except SQLAlchemyError as e:
            pass

        finally:
            database.session.close()



#scheduler
async def tick():
    date = int(datetime.datetime.now().strftime('%H'))
    if  date >= 8 and date <= 20: # send weather only in day-time
        try:
            database = Database()
            all_users = database.session.query(User).filter(User.subscribe).all() #get all users with active subscribe
            for user in all_users:
                chat_id = user.chat_id
                period = user.period
                now = datetime.datetime.now()
                last_update = user.last_update
                next_update = last_update + datetime.timedelta(hours=1*period)
                if now > next_update:
                    weather = request_weather(user.lat, user.lon)
                    user.weather = weather
                    user.last_update = datetime.datetime.now()
                    database.session.commit()
                    await bot.send_message(chat_id, weather, parse_mode='markdown')

        except SQLAlchemyError as e:
            pass

        finally:
            database.session.close()



scheduler = AsyncIOScheduler()
scheduler.add_job(tick, 'interval', seconds=60)
scheduler.start()




if __name__ == '__main__':
    executor.start_polling(dp)
