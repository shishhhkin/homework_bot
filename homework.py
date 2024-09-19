import logging
import os
import sys
import time
from http import HTTPStatus

import requests
from telebot import TeleBot
from telebot.apihelper import ApiTelegramException
from dotenv import load_dotenv

from exceptions import MessageSendingError, MissingTokenError, ResponseError
from settings import ENDPOINT, HOMEWORK_VERDICTS, RETRY_PERIOD

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s -[%(levelname)s]- %(message)s')
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)


def check_tokens() -> bool:
    """Проверяет наличие токенов.

    Returns:
        bool: Выбрасывает исключение если какой-либо токен не существует.
    """
    tokens = (
        PRACTICUM_TOKEN,
        TELEGRAM_TOKEN,
        TELEGRAM_CHAT_ID
    )

    if not all(tokens):
        raise MissingTokenError('Ошибка получения токена')


def send_message(bot, message):
    """Отправляет сообщение message в чат TELEGRAM_CHAT_ID.

    Args:
        bot (TeleBot): Экземпляр класса TeleBot
        message (str): Сообщение для отправки
    """
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(f'Отправлено сообщение "{message}"')
    except ApiTelegramException as e:
        raise MessageSendingError(
            f"Ошибка API Telegram: {e}"
        )
    except requests.exceptions.ConnectionError:
        raise MessageSendingError(
            "Ошибка сети: проверьте подключение к интернету."
        )
    except requests.exceptions.Timeout:
        raise MessageSendingError(
            "Превышено время ожидания ответа от сервера."
        )
    except Exception as e:
        raise MessageSendingError(
            f"Произошла непредвиденная ошибка: {e}"
        )


def get_api_answer(timestamp: int) -> dict:
    """Возвращает ответ от YandexPracticum API.

    Args:
        timestamp (int): Время в формате Unix Timestamp, начиная с которого
        требуется получить записи о домашней работе.

    Returns:
        dict: Ответ API в виде словаря.
    """
    payload = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
    except requests.RequestException as error:
        logger.error(f'Ошибка отправки запроса: {error}')
    if response.status_code != HTTPStatus.OK:
        raise ResponseError(
            f'Получен ответ со статусом {response.status_code}'
        )

    return response.json()


def check_response(response: dict):
    """Проверяет ответ от Yandex API.

    Args:
        response (dict): Ответ от API в виде словаря.

    В функции надо проверить, что полученный от Яндекса ответ это словарь,
    проверить, что в нем есть ключи homeworks и current_date и что при
    обращении с ключом homeworks мы получаем список.
    """
    if not isinstance(response, dict):
        raise TypeError(
            f'Ответ от Yandex API не словарь, а {type(response)}'
        )

    homeworks = response.get('homeworks')

    if homeworks is None:
        raise ResponseError('В ответе от Yandex API нет записей о ДЗ')

    if response.get('current_date') is None:
        raise ResponseError('В ответе от Yandex API нет записи о текущей дате')

    if not isinstance(homeworks, list):
        raise TypeError(
            'В ответе от Yandex API записи о ДЗ не приведены к списку'
        )

    if len(homeworks) < 1:
        raise ResponseError(
            'В ответе от Yandex API список с записями о ДЗ пуст'
        )


def parse_status(homework: dict) -> str:
    """Извлекает из записи о домашней работе её статус.

    Args:
        homework (dict): Запись о домашней работе.

    Returns:
        str: Статус домашней работы.
    """
    homework_name = homework.get('homework_name')

    if homework_name is None:
        raise ResponseError('В ответе API нет ключа homework_name')

    homework_status = homework.get('status')
    verdict = HOMEWORK_VERDICTS.get(homework_status)

    if verdict is None:
        raise ResponseError('Неожиданный статус домашней работы')

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    try:
        check_tokens()
    except MissingTokenError:
        logger.critical('Отсутствует обязательный токен')
        sys.exit(1)

    # Создаем объект класса бота
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_status = ''

    while True:
        try:
            response = get_api_answer(timestamp)
            check_response(response)
            homework = response.get('homeworks')[0]
            status = parse_status(homework)

            if status != last_status:
                send_message(bot, status)
            else:
                logger.debug('Статус не изменился, сообщение не отправлено')

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            send_message(bot, message)

        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
