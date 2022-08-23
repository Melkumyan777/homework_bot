import os
import json
import logging
import time

import requests
import telegram
from dotenv import load_dotenv
from http import HTTPStatus


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s')


load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')


RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)


class SpecialException(Exception):
    """Исключение бота."""

    pass


def send_message(bot, message):
    """Отправка сообщения."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.info(
            f'Удачная отправка сообщения в Telegram: {message}')
    except telegram.TelegramError as telegram_error:
        logger.error(
            f'Сбой при отправке сообщения в Telegram: {telegram_error}')


def get_api_answer(current_timestamp):
    """Запрос к эндпоинту."""
    logger.info('Обращение к серверу')
    timestamp = current_timestamp or int(time.time())
    try:
        homework_status = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp}
        )
    except requests.exceptions.RequestException as error:
        raise SpecialException(f'Ошибка в запросе: {error}')
    except TypeError as error:
        raise SpecialException(f'Неверные данные: {error}')
    except ValueError as error:
        raise SpecialException(f'Ошибка в значении: {error}')

    if homework_status.status_code != HTTPStatus.OK:
        try:
            homework_status_json = homework_status.json()
            logger.error(homework_status_json)
            raise SpecialException('Эндпоинт не отвечает')
        except json.JSONDecodeError:
            raise SpecialException("Ответ не в формате JSON")

    try:
        homework_status_json = homework_status.json()
    except json.JSONDecodeError:
        raise SpecialException("Ответ не в формате JSON")
    logger.info("Получен ответ от сервера")
    return homework_status_json


def check_response(response):
    """Проверка ответа API на корректность."""
    logger.info('Проверка ответа API на корректность')

    if isinstance(response, dict):
        if 'homeworks' not in response.keys():
            raise SpecialException(
                'Отсутствует ключевое значение - "homeworks"')

    if 'error' in response:
        logger.error(response['error'])
        raise SpecialException(response['error'])

    if not isinstance(response['homeworks'], list):
        info = (f'{response["homeworks"]} Не является списком')
        logger.info(info)
        raise SpecialException(info)
    logger.info('Проверка на корректность завершена')

    return response['homeworks']


def parse_status(homework):
    """Получение статуса домашней работы."""
    if 'homework_name' not in homework.keys():
        info_for_parse_status = 'Отсутствует ключ homework_name'
        logger.error(info_for_parse_status)
        raise KeyError(info_for_parse_status)

    if 'status' not in homework.keys():
        info_for_parse_status = 'Отсутствует ключ status'
        logger.error(info_for_parse_status)
        raise KeyError(info_for_parse_status)

    homework_name = homework['homework_name']
    homework_status = homework['status']

    if homework_status not in VERDICTS:
        logger.error('Недокументированный статус домашней работы')
        raise KeyError('Неизвестный статус')
    verdict = VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка доступности переменных окружения."""
    """Если отсутствует хотя бы одна переменная"""
    """окружения — функция должна вернуть False, иначе — True"""
    if (PRACTICUM_TOKEN is None
        or TELEGRAM_TOKEN is None
            or TELEGRAM_CHAT_ID is None):
        logger.critical('Отсутствие обязательных переменных')
        return False
    return True


def main():
    """Основная логика работы бота."""
    logger.info('Запуск бота')
    if not check_tokens():
        return 0
    current_timestamp = int(time.time())
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    homework_old = ''

    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            if isinstance(homeworks, list) and homeworks:
                if homeworks != homework_old:
                    current_homework_status = parse_status(homeworks)
                    send_message(bot, parse_status(current_homework_status))
            else:
                logger.info('Нет заданий')
                current_timestamp = response['current_date']
                time.sleep(RETRY_TIME)

        except SpecialException as error:
            message = f'Сбой в работе программы: {error}'
            logger.critical(message)
            send_message(bot, message)
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
