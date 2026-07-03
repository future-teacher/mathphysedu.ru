"""
Telegram Bot notification module for mathphysedu.ru

Отправляет уведомления в Telegram при создании/проверке домашних заданий и пробников.
Использует Telegram Bot API через HTTP-запросы (без дополнительных зависимостей).

Поддерживает два способа идентификации получателя:
1. Числовой chat_id (надёжнее) — сохраняется после того, как пользователь написал боту
2. @username — используется как запасной вариант

Настройки:
- TELEGRAM_BOT_TOKEN: токен бота (получить у @BotFather)
- TELEGRAM_BOT_ENABLED: включить/выключить уведомления
"""

import logging
import json
from urllib import request as urllib_request
from urllib.error import URLError, HTTPError
from django.conf import settings

logger = logging.getLogger(__name__)



def _resolve_chat_id(recipient):
    """
    Определяет chat_id для отправки сообщения.
    
    Приоритет:
    1. Числовой chat_id (если есть)
    2. @username (если chat_id нет)
    
    Args:
        recipient: объект с полями telegram/telegram_username и telegram_chat_id
                   или строка с @username
    
    Returns:
        str: chat_id для передачи в Telegram API, или None
    """
    if hasattr(recipient, 'telegram_chat_id') and recipient.telegram_chat_id:
        return str(recipient.telegram_chat_id)
    
    if hasattr(recipient, 'telegram_username') and recipient.telegram_username:
        username = recipient.telegram_username.lstrip('@')
        return f'@{username}'
    
    if hasattr(recipient, 'telegram') and recipient.telegram:
        username = recipient.telegram.lstrip('@')
        return f'@{username}'
    
    if isinstance(recipient, str):
        return recipient if recipient.startswith('@') else f'@{recipient.lstrip("@")}'
    
    return None


def _send_telegram_message(recipient, text: str, parse_mode: str = 'HTML') -> bool:
    """
    Отправляет сообщение в Telegram через Bot API.

    Args:
        recipient: объект получателя (Teacher/Student) или строка с @username
        text: Текст сообщения (поддерживает HTML-разметку)
        parse_mode: Режим форматирования ('HTML' или 'Markdown')

    Returns:
        True если сообщение отправлено успешно, иначе False
    """
    if not getattr(settings, 'TELEGRAM_BOT_ENABLED', False):
        logger.debug('Telegram bot is disabled')
        return False

    token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
    if not token:
        logger.warning('TELEGRAM_BOT_TOKEN not configured')
        return False

    chat_id = _resolve_chat_id(recipient)
    if not chat_id:
        logger.warning('Empty chat_id, skipping notification')
        return False

    url = f'https://api.telegram.org/bot{token}/sendMessage'

    payload = json.dumps({
        'chat_id': chat_id,
        'text': text,
        'parse_mode': parse_mode,
        'disable_web_page_preview': True,
    }).encode('utf-8')

    req = urllib_request.Request(
        url,
        data=payload,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )

    try:
        with urllib_request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode('utf-8'))
            if result.get('ok'):
                logger.info(f'Telegram message sent to {chat_id}')
                return True
            else:
                logger.error(
                    f'Telegram API error for {chat_id}: '
                    f'{result.get("description", "Unknown error")}'
                )
                return False
    except HTTPError as e:
        error_body = e.read().decode('utf-8', errors='replace')
        try:
            error_data = json.loads(error_body)
            error_desc = error_data.get('description', str(e))
        except (json.JSONDecodeError, ValueError):
            error_desc = str(e)

        if 'chat not found' in error_desc.lower():
            logger.warning(
                f'Telegram user {chat_id} not found. '
                f'User must start a chat with @MathPhyseduBot first '
                f'(send /start to the bot).'
            )
        else:
            logger.error(f'Telegram API error for {chat_id}: {error_desc}')
        return False
    except URLError as e:
        logger.error(f'Failed to send Telegram message to {chat_id}: {e}')
        return False
    except Exception as e:
        logger.error(f'Unexpected error sending Telegram message: {e}')
        return False


WELCOME_MESSAGE = (
    "🎓 <b>Добро пожаловать в MathPhysEdu Bot!</b>\n\n"
    "Этот бот будет присылать тебе уведомления о:\n\n"
    "📚 <b>Новых домашних заданиях</b> — как только преподаватель выдаст задание\n"
    "📝 <b>Новых пробниках</b> — когда появится новый пробник\n"
    "✅ <b>Результатах проверки</b> — оценка и комментарий преподавателя\n\n"
    "📌 <b>Как работать с домашними заданиями:</b>\n"
    "1. Получи уведомление о новом задании\n"
    "2. Зайди в личный кабинет на сайте и загрузи решение\n"
    "3. Жди результат — мы оповестим тебя в этом боте!\n\n"
    "🔗 <a href=\"{base_url}/students/dashboard/\">Перейти в личный кабинет</a>\n\n"
    "Успехов в учёбе! 🚀"
)


def _send_telegram_raw(token, chat_id, text, parse_mode='HTML'):
    """Отправляет сырое сообщение в Telegram по числовому chat_id."""
    url = f'https://api.telegram.org/bot{token}/sendMessage'
    payload = json.dumps({
        'chat_id': chat_id,
        'text': text,
        'parse_mode': parse_mode,
        'disable_web_page_preview': True,
    }).encode('utf-8')
    req = urllib_request.Request(url, data=payload, headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with urllib_request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except HTTPError as e:
        return json.loads(e.read().decode('utf-8', errors='replace'))


def process_single_update(update_data):
    """
    Обрабатывает одно входящее обновление от Telegram.

    - На команду /start отправляет приветственное сообщение с инструкцией
    - Сохраняет chat_id пользователей

    Может быть вызвана как из polling, так и из webhook.

    Args:
        update_data: dict — одно обновление из Telegram API

    Returns:
        bool: True если обработано успешно
    """
    from students.models import Student, Teacher

    token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
    if not token:
        return False

    base_url = getattr(settings, 'BASE_URL', 'http://127.0.0.1:8000')

    msg = update_data.get('message', {})
    chat = msg.get('chat', {})
    chat_id = chat.get('id')
    text = msg.get('text', '')
    username = (msg.get('from', {}).get('username') or '').lower()

    if not chat_id:
        return False

    # Проверяем команду /start
    if text.strip() == '/start':
        # Отправляем приветствие
        welcome_text = WELCOME_MESSAGE.format(base_url=base_url)
        result = _send_telegram_raw(token, chat_id, welcome_text)
        if result.get('ok'):
            logger.info(f'Sent welcome to @{username} (chat_id={chat_id})')

        # Сохраняем chat_id в модели (если есть username)
        if username:
            # Ищем преподавателя
            teacher = Teacher.objects.filter(telegram__iexact=f'@{username}').first()
            if teacher:
                if teacher.telegram_chat_id != chat_id:
                    teacher.telegram_chat_id = chat_id
                    teacher.save(update_fields=['telegram_chat_id'])
                    logger.info(f'Saved chat_id for teacher {teacher.user.username}')

            # Ищем ученика
            student = Student.objects.filter(telegram_username__iexact=f'@{username}').first()
            if student:
                if student.telegram_chat_id != chat_id:
                    student.telegram_chat_id = chat_id
                    student.save(update_fields=['telegram_chat_id'])
                    logger.info(f'Saved chat_id for student {student.first_name} {student.last_name}')

        return True

    return False


def process_updates():
    """
    Обрабатывает входящие сообщения от Telegram Bot API (polling).

    - На команду /start отправляет приветственное сообщение с инструкцией
    - Сохраняет chat_id пользователей

    Запускается через management command:
        python manage.py telegram_polling
    """
    token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
    if not token:
        logger.warning('TELEGRAM_BOT_TOKEN not configured')
        return

    url = f'https://api.telegram.org/bot{token}/getUpdates'
    req = urllib_request.Request(url)

    try:
        with urllib_request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode('utf-8'))
    except Exception as e:
        logger.error(f'Failed to get updates: {e}')
        return

    if not data.get('ok'):
        logger.error('Telegram API error: %s', data.get('description'))
        return

    processed = 0

    for update in data.get('result', []):
        if process_single_update(update):
            processed += 1

    logger.info(f'Polling complete. Processed: {processed}')
    return processed


def sync_telegram_chat_ids():
    """
    Синхронизирует chat_id из getUpdates с моделями Student и Teacher.
    
    Запускается через management command:
        python manage.py sync_telegram_chat_ids
    
    Ищет пользователей, которые писали боту, и сохраняет их числовой chat_id
    в соответствующие модели (по совпадению @username).
    """
    from students.models import Student, Teacher
    
    token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
    if not token:
        logger.warning('TELEGRAM_BOT_TOKEN not configured, cannot sync')
        return
    
    url = f'https://api.telegram.org/bot{token}/getUpdates'
    req = urllib_request.Request(url)
    
    try:
        with urllib_request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode('utf-8'))
    except Exception as e:
        logger.error(f'Failed to get updates: {e}')
        return
    
    if not data.get('ok'):
        logger.error('Telegram API error: %s', data.get('description'))
        return
    
    # Собираем уникальные пары username -> chat_id
    chat_map = {}  # username -> chat_id
    for update in data.get('result', []):
        # Из message
        msg = update.get('message', {})
        if msg.get('from', {}).get('username'):
            username = msg['from']['username'].lower()
            chat_id = msg['from']['id']
            chat_map[username] = chat_id
        
        # Из my_chat_member
        mcm = update.get('my_chat_member', {})
        if mcm.get('chat', {}).get('username'):
            username = mcm['chat']['username'].lower()
            chat_id = mcm['chat']['id']
            chat_map[username] = chat_id
    
    updated_count = 0
    
    # Обновляем Teacher
    for teacher in Teacher.objects.all():
        if teacher.telegram:
            username = teacher.telegram.lstrip('@').lower()
            if username in chat_map:
                chat_id = chat_map[username]
                if teacher.telegram_chat_id != chat_id:
                    teacher.telegram_chat_id = chat_id
                    teacher.save(update_fields=['telegram_chat_id'])
                    logger.info(f'Updated Teacher {teacher.user.username}: chat_id={chat_id}')
                    updated_count += 1
    
    # Обновляем Student
    for student in Student.objects.all():
        if student.telegram_username:
            username = student.telegram_username.lstrip('@').lower()
            if username in chat_map:
                chat_id = chat_map[username]
                if student.telegram_chat_id != chat_id:
                    student.telegram_chat_id = chat_id
                    student.save(update_fields=['telegram_chat_id'])
                    logger.info(f'Updated Student {student.first_name} {student.last_name}: chat_id={chat_id}')
                    updated_count += 1
    
    logger.info(f'Sync complete. Updated {updated_count} records.')
    return updated_count


# ========================
# УВЕДОМЛЕНИЯ УЧЕНИКАМ
# ========================


def notify_student_new_homework(homework) -> bool:
    """
    Уведомляет ученика о новом домашнем задании.

    Args:
        homework: экземпляр модели Homework
    """
    student = homework.student
    subject_display = homework.get_subject_display()
    deadline_str = (
        homework.deadline.strftime('%d.%m.%Y') if homework.deadline else 'Не указан'
    )

    text = (
        f"📚 <b>Новое домашнее задание!</b>\n\n"
        f"<b>Предмет:</b> {subject_display}\n"
        f"<b>Название:</b> {homework.title}\n"
        f"<b>Дедлайн:</b> {deadline_str}\n\n"
        f"🔗 <a href=\"{settings.BASE_URL}/students/homework/{homework.id}/\">"
        f"Открыть задание</a>"
    )

    # Отправляем ученику (используем объект student для определения chat_id)
    sent_to_student = _send_telegram_message(student, text)

    # Отправляем родителю, если указан
    sent_to_parent = False
    if student.parent_telegram:
        parent_text = (
            f"📚 <b>Новое домашнее задание для {student.first_name}!</b>\n\n"
            f"<b>Предмет:</b> {subject_display}\n"
            f"<b>Название:</b> {homework.title}\n"
            f"<b>Дедлайн:</b> {deadline_str}\n\n"
            f"🔗 <a href=\"{settings.BASE_URL}/students/homework/{homework.id}/\">"
            f"Открыть задание</a>"
        )
        sent_to_parent = _send_telegram_message(
            student.parent_telegram, parent_text
        )

    return sent_to_student or sent_to_parent


def notify_student_homework_checked(homework) -> bool:
    """
    Уведомляет ученика о проверке домашнего задания.

    Args:
        homework: экземпляр модели Homework (уже сохранён с оценкой)
    """
    student = homework.student
    subject_display = homework.get_subject_display()
    grade_display = homework.get_grade_display_formatted()

    text = (
        f"✅ <b>Домашнее задание проверено!</b>\n\n"
        f"<b>Предмет:</b> {subject_display}\n"
        f"<b>Название:</b> {homework.title}\n"
        f"<b>Оценка:</b> {grade_display}\n"
    )

    if homework.teacher_comment:
        text += f"\n<b>Комментарий:</b>\n{homework.teacher_comment}\n"

    text += (
        f"\n🔗 <a href=\"{settings.BASE_URL}/students/homework/{homework.id}/\">"
        f"Посмотреть</a>"
    )

    sent_to_student = _send_telegram_message(student, text)

    sent_to_parent = False
    if student.parent_telegram:
        parent_text = (
            f"✅ <b>Домашнее задание {student.first_name} проверено!</b>\n\n"
            f"<b>Предмет:</b> {subject_display}\n"
            f"<b>Название:</b> {homework.title}\n"
            f"<b>Оценка:</b> {grade_display}\n"
        )
        if homework.teacher_comment:
            parent_text += f"\n<b>Комментарий:</b>\n{homework.teacher_comment}\n"
        parent_text += (
            f"\n🔗 <a href=\"{settings.BASE_URL}/students/homework/{homework.id}/\">"
            f"Посмотреть</a>"
        )
        sent_to_parent = _send_telegram_message(
            student.parent_telegram, parent_text
        )

    return sent_to_student or sent_to_parent


def notify_student_new_probnik(probnik) -> bool:
    """
    Уведомляет ученика о новом пробнике.

    Args:
        probnik: экземпляр модели Probnik
    """
    student = probnik.student
    subject_display = probnik.get_subject_display()
    deadline_str = (
        probnik.deadline.strftime('%d.%m.%Y') if probnik.deadline else 'Не указан'
    )
    month_display = probnik.get_month_display() if probnik.month else None

    text = (
        f"📝 <b>Новый пробник!</b>\n\n"
        f"<b>Предмет:</b> {subject_display}\n"
        f"<b>Название:</b> {probnik.title}\n"
    )
    if month_display:
        text += f"<b>Месяц:</b> {month_display}\n"
    text += (
        f"<b>Дедлайн:</b> {deadline_str}\n"
        f"🔗 <a href=\"{settings.BASE_URL}/students/probnik/{probnik.id}/\">"
        f"Открыть пробник</a>"
    )

    sent_to_student = _send_telegram_message(student, text)

    sent_to_parent = False
    if student.parent_telegram:
        parent_text = (
            f"📝 <b>Новый пробник для {student.first_name}!</b>\n\n"
            f"<b>Предмет:</b> {subject_display}\n"
            f"<b>Название:</b> {probnik.title}\n"
        )
        if month_display:
            parent_text += f"<b>Месяц:</b> {month_display}\n"
        parent_text += (
            f"<b>Дедлайн:</b> {deadline_str}\n"
            f"🔗 <a href=\"{settings.BASE_URL}/students/probnik/{probnik.id}/\">"
            f"Открыть пробник</a>"
        )
        sent_to_parent = _send_telegram_message(
            student.parent_telegram, parent_text
        )

    return sent_to_student or sent_to_parent


def notify_student_probnik_checked(probnik) -> bool:
    """
    Уведомляет ученика о проверке пробника.

    Args:
        probnik: экземпляр модели Probnik (уже сохранён с оценкой)
    """
    student = probnik.student
    subject_display = probnik.get_subject_display()
    grade_display = probnik.get_grade_display() or '—'
    percentage = probnik.get_percentage()

    text = (
        f"✅ <b>Пробник проверен!</b>\n\n"
        f"<b>Предмет:</b> {subject_display}\n"
        f"<b>Название:</b> {probnik.title}\n"
        f"<b>Результат:</b> {probnik.score}/{probnik.max_score}"
    )
    if percentage is not None:
        text += f" ({percentage}%)"
    text += f"\n<b>Оценка:</b> {grade_display}\n"

    if probnik.teacher_comment:
        text += f"\n<b>Комментарий:</b>\n{probnik.teacher_comment}\n"

    text += (
        f"\n🔗 <a href=\"{settings.BASE_URL}/students/probnik/{probnik.id}/\">"
        f"Посмотреть</a>"
    )

    sent_to_student = _send_telegram_message(student, text)

    sent_to_parent = False
    if student.parent_telegram:
        parent_text = (
            f"✅ <b>Пробник {student.first_name} проверен!</b>\n\n"
            f"<b>Предмет:</b> {subject_display}\n"
            f"<b>Название:</b> {probnik.title}\n"
            f"<b>Результат:</b> {probnik.score}/{probnik.max_score}"
        )
        if percentage is not None:
            parent_text += f" ({percentage}%)"
        parent_text += f"\n<b>Оценка:</b> {grade_display}\n"
        if probnik.teacher_comment:
            parent_text += f"\n<b>Комментарий:</b>\n{probnik.teacher_comment}\n"
        parent_text += (
            f"\n🔗 <a href=\"{settings.BASE_URL}/students/probnik/{probnik.id}/\">"
            f"Посмотреть</a>"
        )
        sent_to_parent = _send_telegram_message(
            student.parent_telegram, parent_text
        )

    return sent_to_student or sent_to_parent


# ========================
# УВЕДОМЛЕНИЯ ПРЕПОДАВАТЕЛЮ
# ========================


def notify_teacher_homework_submitted(homework) -> bool:
    """
    Уведомляет преподавателя о том, что ученик загрузил/обновил файлы ДЗ.

    Args:
        homework: экземпляр модели Homework
    """
    teacher = homework.assigned_by
    if not teacher:
        logger.warning(
            f'Cannot notify teacher: homework {homework.id} has no assigned teacher'
        )
        return False

    # Проверяем, есть ли способ отправить уведомление (chat_id или telegram username)
    if not teacher.telegram_chat_id and not teacher.telegram:
        logger.warning(
            f'Cannot notify teacher {teacher.user.username}: '
            f'no telegram_chat_id and no telegram username configured. '
            f'Teacher needs to fill in their Telegram username in profile settings '
            f'and send /start to @MathPhyseduBot.'
        )
        return False

    student = homework.student
    subject_display = homework.get_subject_display()

    text = (
        f"👨‍🎓 <b>Ученик добавил файлы к ДЗ!</b>\n\n"
        f"<b>Ученик:</b> {student.first_name} {student.last_name}\n"
        f"<b>Предмет:</b> {subject_display}\n"
        f"<b>Название:</b> {homework.title}\n"
        f"<b>Файлов в решении:</b> {homework.get_student_files_count()}\n\n"
        f"🔗 <a href=\"{settings.BASE_URL}/students/teacher/homework/{homework.id}/\">"
        f"Проверить</a>"
    )

    result = _send_telegram_message(teacher, text)
    if result:
        logger.info(
            f'Notification sent to teacher {teacher.user.username} '
            f'about homework {homework.id} from student {student.first_name} {student.last_name}'
        )
    return result


def notify_teacher_probnik_submitted(probnik) -> bool:
    """
    Уведомляет преподавателя о том, что ученик отправил пробник на проверку.

    Args:
        probnik: экземпляр модели Probnik
    """
    teacher = probnik.assigned_by
    if not teacher:
        logger.warning(
            f'Cannot notify teacher: probnik {probnik.id} has no assigned teacher'
        )
        return False

    # Проверяем, есть ли способ отправить уведомление (chat_id или telegram username)
    if not teacher.telegram_chat_id and not teacher.telegram:
        logger.warning(
            f'Cannot notify teacher {teacher.user.username}: '
            f'no telegram_chat_id and no telegram username configured. '
            f'Teacher needs to fill in their Telegram username in profile settings '
            f'and send /start to @MathPhyseduBot.'
        )
        return False

    student = probnik.student
    subject_display = probnik.get_subject_display()

    text = (
        f"👨‍🎓 <b>Ученик отправил пробник на проверку!</b>\n\n"
        f"<b>Ученик:</b> {student.first_name} {student.last_name}\n"
        f"<b>Предмет:</b> {subject_display}\n"
        f"<b>Название:</b> {probnik.title}\n"
        f"<b>Файлов в решении:</b> {probnik.get_student_files_count()}\n\n"
        f"🔗 <a href=\"{settings.BASE_URL}/students/teacher/probnik/{probnik.id}/\">"
        f"Проверить</a>"
    )

    result = _send_telegram_message(teacher, text)
    if result:
        logger.info(
            f'Notification sent to teacher {teacher.user.username} '
            f'about probnik {probnik.id} from student {student.first_name} {student.last_name}'
        )
    return result