import logging
import os
import random
import sys
import time
from http import HTTPStatus

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
    '%(asctime)s, %(name)s, %(levelname)s, %(message)s, %(filename)s',
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
    tokens = [
        name for name, token in
        (
            ('VK_TOKEN', VK_TOKEN),
            ('PRACTICUM_TOKEN', PRACTICUM_TOKEN),
            ('VK_USER_ID', VK_USER_ID),
        ) if not token
    ]
    if tokens:
        logger.critical(f"Отсутствует токен: {' '.join(tokens)}")
    return tokens


def send_message(vk, message):
    """Отправляет сообщение пользователю VK."""
    try:
        vk.messages.send(
            user_id=VK_USER_ID,
            message=message,
            random_id=random.randint(0, 100000),
        )
        logger.debug('Сообщение успешно отправлено.')
        return True
    except Exception as error:
        logger.error(
            f'Произошла ошибка при отправке сообщения: {error}',
        )
        return False


def get_api_answer(timestamp):
    """Получает ответ от API Практикума."""
    params = {'from_date': timestamp}
    logger.debug(
        'Начинается отправка API запроса. '
        f'По адресу: {ENDPOINT}. Параметры запроса: {params}',
    )
    try:
        response = requests.get(
            ENDPOINT,
            params=params,
            headers=HEADERS,
        )
    except requests.RequestException as error:
        raise ConnectionError(
            f'Ошибка при запросе к API: {error}. '
            f'Адрес, на который отправляли запрос: {ENDPOINT}. '
            f'Параметры запроса: {params}.',
        )

    if response.status_code != HTTPStatus.OK:
        raise ValueError(
            f'Код ответа API: {response.status_code}',
        )
    logger.debug(
        f'Запрос к API успешно завершен. '
        f'По адресу: {ENDPOINT}. С параметрами: {params}',
    )

    return response.json()


def check_response(response):
    """Проверяет корректность структуры ответа API."""
    logger.debug('Началась проверка ответа сервера.')
    if not isinstance(response, dict):
        raise TypeError(
            'Некорректный тип данных '
            f'{type(response).__name__}',
        )

    if 'homeworks' not in response:
        raise KeyError('Отсутствует ключ homeworks')

    if not isinstance(response['homeworks'], list):
        raise TypeError(
            'Некорректный тип данных(homeworks) '
            f'{type(response["homeworks"]).__name__}',
        )
    logger.debug('Ответ сервера успешно прошёл проверку.')


def parse_status(homework):
    """Формирует сообщение об изменении статуса домашней работы."""
    logger.debug('Началась проверка статуса домашней работы.')
    if 'homework_name' not in homework:
        raise KeyError('Отсутствует ключ homework_name')

    if 'status' not in homework:
        raise KeyError('Отсутствует ключ status')

    status = homework['status']

    if status not in HOMEWORK_VERDICTS:
        raise ValueError(f'Неизвестный статус домашней работы: {status}')

    homework_name = homework['homework_name']
    verdict = HOMEWORK_VERDICTS[status]

    logger.debug('Статус домашней работы успешно проверен.')
    return (
        f'Изменился статус проверки работы "{homework_name}". {verdict}'
    )


def main():
    """Основная логика работы бота."""
    if check_tokens():
        raise SystemExit('Ошибка запуска: проверьте переменные окружения.')

    timestamp = int(time.time())

    # Создаем сессию для бота
    vk_session = vk_api.VkApi(token=VK_TOKEN)
    vk = vk_session.get_api()

    last_departures = None

    while True:
        try:
            response = get_api_answer(timestamp)
            check_response(response)
            homeworks = response['homeworks']

            if not homeworks:
                logger.debug('Нет новых статусов домашних работ.')
            else:
                message = parse_status(homeworks[0])
                if send_message(vk, message):
                    last_departures = message

            timestamp = response.get('current_date', int(time.time()))
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if last_departures != message:
                if send_message(vk, message):
                    last_departures = message
            logger.error(message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
