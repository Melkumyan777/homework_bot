
from http import HTTPStatus
import json
import logging
import os
import time
import requests
import telegram
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')


RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)


class Exception(Exception):
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
    timestamp = current_timestamp or int(time.time())
    try:
        homework_status = requests.get(
            ENDPOINT,
            headers={'Authorization': f'OAuth {PRACTICUM_TOKEN}'},
            params={'from_date': timestamp}
        )
    except requests.exceptions.RequestException as error:
        raise Exception(f'Ошибка в запросе: {error}')
    except TypeError as error:
        raise Exception(f'Неверные данные: {error}')

    if homework_status.status_code != HTTPStatus.OK:
        logger.error(homework_status.json())
        raise Exception('Ошибка по эндпоинту')

    try:
        homework_status_json = homework_status.json()
    except json.JSONDecodeError:
        raise Exception("Ответ не в формате JSON")
    return homework_status_json


def check_response(response):
    """Проверка ответа API на корректность."""
    logger.info('Проверка ответа API на корректность')

    if isinstance(response, dict):
        if 'homeworks' not in response.keys():
            raise Exception('Отсутствует ключевое значение - "homeworks"')

    if 'error' in response:
        logger.error(response['error'])
        raise Exception(response['error'])

    if response['homeworks'] is None:
        logger.info('Нет заданий')
        raise Exception('Нет заданий')

    if not isinstance(response['homeworks'], list):
        logger.info(f'{response["homeworks"]} Не является списком')
        raise Exception(f'{response["homeworks"]} Не является списком')
    logger.info('Проверка на корректность завершена')
    return response['homeworks']


def parse_status(homework):
    if 'homework_name' not in homework.keys():
        logger.error('Отсутствует ключ для homework_name')
        raise KeyError('Отсутствует ключ для тhomework_name')

    if 'status' not in homework.keys():
        logger.error('Отсутствует ключ для status')
        raise KeyError('Отсутствует ключ для status')

    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')

    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'

def check_tokens():
    """Проверка доступности переменных окружения. 
    Если отсутствует хотя бы одна переменная
    окружения — функция должна вернуть False, иначе — True"""
    if (PRACTICUM_TOKEN is None
        or TELEGRAM_TOKEN is None
            or TELEGRAM_CHAT_ID is None):
        logger.critical(
            'Отсутствие обязательных переменных')
        return False
    return True


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())

    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            if type(homeworks) is list:
                send_message(bot, parse_status(homeworks[0]))
            else:
                current_timestamp = response['current_date']
                time.sleep(RETRY_TIME)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.critical(message)
            send_message(bot, message)
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
