"""
Yandex SmartCaptcha validation helper.

Документация: https://yandex.cloud/ru/docs/smartcaptcha/quick-start#validate
"""
import logging
import urllib.request
import urllib.parse
import json

from django.conf import settings

logger = logging.getLogger(__name__)

# URL для проверки токена капчи
SMARTCAPTCHA_VALIDATE_URL = 'https://smartcaptcha.yandexcloud.net/validate'


def check_captcha(token: str, ip: str | None = None) -> bool:
    """
    Проверяет токен Yandex SmartCaptcha через серверный ключ.

    Аргументы:
        token: токен, полученный от виджета на клиенте (smart-token)
        ip: IP-адрес пользователя (опционально, для дополнительной проверки)

    Возвращает:
        True, если капча пройдена успешно, иначе False.
    """
    if not token:
        logger.warning('Yandex SmartCaptcha: пустой токен')
        return False

    server_key = settings.YANDEX_SMARTCAPTCHA_SERVER_KEY

    # Проверяем, что ключи не являются заглушками
    if 'placeholder' in server_key:
        logger.warning(
            'Yandex SmartCaptcha: серверный ключ не настроен '
            '(используется значение-заглушка). Капча пропущена.'
        )
        return True  # Пропускаем проверку в режиме разработки

    params = {
        'secret': server_key,
        'token': token,
    }
    if ip:
        params['ip'] = ip

    try:
        data = urllib.parse.urlencode(params).encode('utf-8')
        req = urllib.request.Request(
            SMARTCAPTCHA_VALIDATE_URL,
            data=data,
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            result = json.loads(response.read().decode('utf-8'))

        if result.get('status') == 'ok':
            return True

        logger.warning(
            'Yandex SmartCaptcha: проверка не пройдена. '
            'Ответ сервера: %s',
            result
        )
        return False

    except (urllib.error.URLError, json.JSONDecodeError, OSError) as exc:
        logger.error(
            'Yandex SmartCaptcha: ошибка при проверке токена: %s', exc
        )
        # При ошибке сети НЕ пропускаем — лучше отказать, чем пропустить бота
        return False