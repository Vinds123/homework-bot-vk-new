import logging
import os
import random
import sys
import time

import requests
import vk_api
from dotenv import load_dotenv


load_dotenv()
PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
VK_TOKEN = os.getenv('VK_TOKEN')
VK_USER_ID = os.getenv('VK_USER_ID')

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
logger.addHandler(handler)
formatter = logging.Formatter(
    '%(asctime)s, %(levelname)s, %(message)s',
)
handler.setFormatter(formatter)

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.',
}


def check_tokens():
    """Проверяет наличие обязательных токенов окружения."""
    if not VK_TOKEN:
        logger.critical('Не найден VK токен.')
        raise Exception('Не найден VK токен.')

    if not PRACTICUM_TOKEN:
        logger.critical('Не найден Практикум токен.')
        raise Exception('Не найден Практикум токен.')

    if not VK_USER_ID:
        logger.critical('ID клиента не найдено.')
        raise Exception('ID клиента не найдено.')


def send_message(vk, message):
    """Отправляет сообщение пользователю VK."""
    vk.messages.send(
        user_id=VK_USER_ID,
        message=message,
        random_id=random.randint(0, 100000),
    )
    logger.debug('Сообщение успешно отправлено.')


def get_api_answer(timestamp):
    """Получает ответ от API Практикума."""
    try:
        response = requests.get(
            ENDPOINT,
            params={'from_date': timestamp},
            headers=HEADERS,
        )
    except requests.RequestException as error:
        logger.error(f'Ошибка при запросе к API: {error}')
        return None

    if response.status_code != 200:
        raise requests.HTTPError(
            f'Код ответа API: {response.status_code}',
        )

    return response.json()


def check_response(response):
    """Проверяет корректность структуры ответа API."""
    if not isinstance(response, dict):
        logger.error('Некорректный тип данных')
        raise TypeError('Некорректный тип данных')

    if 'homeworks' not in response:
        logger.error('Отсутствует ключ homeworks')
        raise KeyError('Отсутствует ключ homeworks')

    if 'current_date' not in response:
        logger.error('Отсутствует ключ current_date')
        raise KeyError('Отсутствует ключ current_date')

    if not isinstance(response['homeworks'], list):
        logger.error('Некорректный тип данных(homeworks)')
        raise TypeError('Некорректный тип данных(homeworks)')

    if not isinstance(response['current_date'], int):
        logger.error('Некорректный тип данных(current_date)')
        raise TypeError('Некорректный тип данных(current_date)')

    return response


def parse_status(homework):
    """Формирует сообщение об изменении статуса домашней работы."""
    if 'homework_name' not in homework:
        raise KeyError('Отсутствует ключ homework_name')

    if 'status' not in homework:
        raise KeyError('Отсутствует ключ status')

    status = homework['status']

    if status not in HOMEWORK_VERDICTS:
        raise ValueError(f'Неизвестный статус домашней работы: {status}')

    homework_name = homework['homework_name']
    verdict = HOMEWORK_VERDICTS[status]

    return (
        f'Изменился статус проверки работы "{homework_name}". {verdict}'
    )


def main():
    """Основная логика работы бота."""
    check_tokens()
    timestamp = int(time.time())

    # Создаем сессию для бота
    vk_session = vk_api.VkApi(token=VK_TOKEN)
    vk = vk_session.get_api()

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)['homeworks']

            if not homeworks:
                logger.debug('Нет новых статусов домашних работ.')

            for homework in homeworks:
                message = parse_status(homework)
                send_message(vk, message)
            timestamp = response['current_date']
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
