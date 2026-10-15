# Margo Love Back

FastAPI + aiogram 3, Python 3.14.

## Запуск (WSL)

Если сборка зависимостей сообщает об отсутствии cc:
sudo apt update && sudo apt install -y build-essential

    uv python install 3.14
    uv sync
    cp .env.example .env

Заполните TELEGRAM_BOT_TOKEN (из @BotFather) и TELEGRAM_CHAT_ID в .env.
Откройте бота и отправьте /start перед отправкой в личный чат.
Для группы добавьте бота с правом отправки сообщений.
chat_id находится в message.chat.id ответа Telegram getUpdates после
сообщения боту (если для него не установлен webhook).

    uv run uvicorn app.main:app --reload --host 127.0.0.1

Swagger: http://127.0.0.1:8000/docs

## API

POST /api/v1/messages
Content-Type: application/json

    {"text": "Привет из payload!"}

Успех: {"ok": true, "message_id": 42} — идентификатор выдан Telegram.
Текст отправляется без изменения, без HTML/Markdown-разметки.
Пустой текст и превышение 4096 единиц UTF-16 возвращают 422.
Ошибка Telegram возвращает 502. После сетевого сбоя результат доставки
может быть неопределённым; повторная отправка может создать дубликат.

## Запросы из браузера

CORS разрешает прямые POST-запросы с https://super-secret-margo-1488.vercel.app
без cookies и credentials. Preflight OPTIONS обрабатывается автоматически;
разрешён заголовок Content-Type для JSON. Фронтенд отправляет логи напрямую
на /api/v1/messages. Изменение начнёт работать после деплоя бэкенда на Vercel.

## Архитектура

- app/api: HTTP, валидация и зависимости.
- app/application: сценарий отправки.
- app/domain: интерфейс отправителя и ошибка доставки.
- app/infrastructure: адаптер aiogram.
- app/core: настройки окружения.
- app/main.py: сборка и жизненный цикл приложения.

Клиент бота создаётся при старте и закрывается при остановке.
Polling и webhook для исходящей отправки не нужны.
Секреты задаются через .env или переменные окружения.
Роут предназначен для локального использования. Перед публикацией
добавьте авторизацию и ограничение запросов.

## Тесты

    uv sync --dev
    uv run python -m unittest discover -s tests -v

Telegram подменяется в тестах, реальные сообщения не отправляются.
## Деплой на Vercel

1. Загрузите проект в GitHub и импортируйте репозиторий в Vercel (Add New Project).
2. Выберите Framework Preset: FastAPI; Root Directory: корень репозитория.
   Build Command и Install Command оставьте стандартными.
   Команда запуска uvicorn на Vercel не нужна.
3. В Environment Variables добавьте TELEGRAM_BOT_TOKEN и TELEGRAM_CHAT_ID.
   Для Production и Preview задайте значения отдельно, если нужны оба окружения.
   Файл .env загружать не нужно.
4. Нажмите Deploy. После изменения переменных окружения выполните Redeploy.

Python 3.14 задан в .python-version и pyproject.toml; зависимости закреплены в uv.lock.
Точка входа явно задана как app.main:app. vercel.json ограничивает выполнение
функции 30 секундами; запрос к Telegram ограничен 10 секундами.

Проверка после деплоя: https://<project>.vercel.app/docs
Роут: POST https://<project>.vercel.app/api/v1/messages

Hobby предназначен для личных некоммерческих проектов и имеет лимиты.
В текущей версии роут без авторизации: до публичного использования
защитите его API-ключом или другим механизмом доступа.
## Серверные логи

Логи приложения выводятся в stderr в едином формате:

```text
2026-10-15T10:30:00.123Z | INFO     | app.api.middleware | request_id=... | HTTP request completed | method=POST route=/api/v1/messages status=200 duration_ms=123.4
```

Время указано в UTC (`Z`) с миллисекундами. Один `request_id` связывает
HTTP-запрос и отправку в Telegram; он также возвращается в заголовке
`X-Request-ID`. Для HTTP 4xx используется WARNING, для 5xx — ERROR.
Отдельно фиксируются запуск, остановка, начало отправки, результат и длительность
обращения к Telegram. Текст сообщения, токен, параметры URL и ID чата не логируются.
JSON запроса и ответа API не изменён: существующий фронтенд совместим.


## Надёжные события и уведомления

1. Создайте PostgreSQL в Neon через Vercel Marketplace и подключите к **margo-log**.
2. Проверьте наличие DATABASE_URL в окружении бэкенда. Не добавляйте его во фронт.
3. Выполните migrations/001_site_events.sql в SQL Editor Neon.
4. Задеплойте сначала бэкенд, затем фронтенд.

POST /api/v1/events возвращает 202 только после фиксации события в PostgreSQL.
Контракт: event_id (UUID), session_id, sequence, name, occurred_at (ISO 8601), text.
Повторный event_id не создаёт ещё одно событие. Текст проверяется как в /messages.
Существующий /api/v1/messages сохранён для совместимости.

Все события сохраняются; Telegram получает visit, open, 100, gallery_open,
question_shown и meeting_yes. Прочие действия можно смотреть в таблице site_events,
сортируя по session_id и sequence. Текст и User-Agent содержатся в text.

Каждое успешно сохранённое событие запускает одну фоновую попытку отправки
самого старого доступного уведомления из очереди, включая ранее неотправленные.
После ошибки уведомление остаётся в базе с экспоненциальной задержкой повтора.
Когда задержка истечёт, повтор запускается при следующем событии на сайте.
Если новых событий нет, очередь ждёт следующего посещения; автономной отправки нет.
Аренда записи на 60 секунд и SKIP LOCKED защищают от параллельной обработки.
Доставка имеет семантику at-least-once: при сбое после отправки в Telegram,
но до записи результата, уведомление может повториться. Событие в базе не дублируется.

Фронтенд по умолчанию отправляет события в /api/v1/events.
NEXT_PUBLIC_EVENT_STORAGE_ENABLED=false включает прежний /api/v1/messages для отката.
После изменения переменной нужен redeploy фронтенда.
Неподтверждённые события хранятся в localStorage и повторяются с тем же event_id.
При блокировке/очистке хранилища браузером несохранённые события могут потеряться.
