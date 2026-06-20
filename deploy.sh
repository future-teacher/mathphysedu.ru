#!/bin/bash

# ============================================
# Скрипт обновления сайта mathphysedu.ru
# ============================================

# Цвета
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}📚 ОБНОВЛЕНИЕ MATHPHYSEDU.RU${NC}"
echo -e "${BLUE}========================================${NC}"

# Переходим в папку проекта
cd /var/www/mathphysedu || exit 1

# 1. ЗАБИРАЕМ ИЗМЕНЕНИЯ ИЗ GIT
echo -e "${YELLOW}📦 Загрузка изменений с GitHub...${NC}"
git fetch origin

# Проверяем, есть ли изменения
LOCAL=$(git rev-parse HEAD 2>/dev/null)
REMOTE=$(git rev-parse origin/master 2>/dev/null)

if [ "$LOCAL" = "$REMOTE" ]; then
    echo -e "${GREEN}✅ Нет новых обновлений. Сайт уже актуален.${NC}"
else
    echo -e "${YELLOW}📥 Обнаружены изменения, загружаем...${NC}"
    git pull origin master
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ Ошибка при загрузке изменений!${NC}"
        echo -e "${YELLOW}💡 Попробуйте выполнить вручную:${NC}"
        echo -e "  cd /var/www/mathphysedu && git pull origin master"
        exit 1
    fi
    echo -e "${GREEN}✅ Изменения загружены${NC}"
fi

# 2. АКТИВИРУЕМ ВИРТУАЛЬНОЕ ОКРУЖЕНИЕ
echo -e "${YELLOW}🔍 Активация виртуального окружения...${NC}"
source venv/bin/activate

# 3. ОБНОВЛЯЕМ ЗАВИСИМОСТИ (если изменились)
if git diff --name-only HEAD~1 HEAD 2>/dev/null | grep -q "requirements"; then
    echo -e "${YELLOW}📦 Обновление зависимостей...${NC}"
    pip install -r requirements.txt
fi

# 4. ПРИМЕНЯЕМ МИГРАЦИИ
echo -e "${YELLOW}🔄 Применение миграций...${NC}"
python manage.py makemigrations
python manage.py migrate

# 5. СОБИРАЕМ СТАТИКУ
echo -e "${YELLOW}📁 Сбор статики...${NC}"
python manage.py collectstatic --noinput

# 6. СИНХРОНИЗАЦИЯ TELEGRAM
echo -e "${YELLOW}🤖 Синхронизация Telegram...${NC}"

# Синхронизируем chat_id пользователей, которые уже писали боту
python manage.py sync_telegram_chat_ids 2>/dev/null || echo -e "${YELLOW}⚠️ Telegram бот не активен (токен не задан)${NC}"

# Отправляем приветствие тем, кто написал /start
python manage.py telegram_polling 2>/dev/null || echo -e "${YELLOW}⚠️ Telegram polling пропущен${NC}"

echo -e "${GREEN}✅ Telegram бот синхронизирован${NC}"

# 7. ВЫХОДИМ ИЗ ВИРТУАЛЬНОГО ОКРУЖЕНИЯ
deactivate

# 8. ОЧИЩАЕМ КЭШ
echo -e "${YELLOW}🧹 Очистка кэша...${NC}"
find . -name "*.pyc" -delete 2>/dev/null
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null

# 9. ПЕРЕЗАПУСКАЕМ GUNICORN
echo -e "${YELLOW}♻️ Перезапуск Gunicorn...${NC}"
sudo systemctl restart gunicorn-mathphysedu

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Ошибка при перезапуске Gunicorn!${NC}"
    echo -e "${YELLOW}📋 Логи ошибок:${NC}"
    sudo journalctl -u gunicorn-mathphysedu -n 20 --no-pager
    exit 1
fi
echo -e "${GREEN}✅ Gunicorn перезапущен${NC}"

# 10. ПРОВЕРЯЕМ РАБОТУ САЙТА
echo -e "${YELLOW}🔍 Проверка работы сайта...${NC}"
sleep 2

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -I https://mathphysedu.ru 2>/dev/null)

if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "301" ] || [ "$HTTP_CODE" = "302" ]; then
    echo -e "${GREEN}✅ Сайт работает! (HTTP $HTTP_CODE)${NC}"
else
    echo -e "${RED}⚠️ Сайт вернул код: $HTTP_CODE${NC}"
    echo -e "${YELLOW}📋 Логи ошибок:${NC}"
    sudo journalctl -u gunicorn-mathphysedu -n 20 --no-pager
fi

# 11. ПОСЛЕДНИЕ КОММИТЫ
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}📋 Последние обновления:${NC}"
git log --oneline -3

# 12. ОТОБРАЖАЕМ ИТОГ
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}✅ Обновление mathphysedu.ru завершено!${NC}"
echo -e "${GREEN}🌐 Сайт: https://mathphysedu.ru${NC}"
echo -e "${BLUE}========================================${NC}"