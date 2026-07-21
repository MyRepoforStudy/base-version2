# Linux Server Inventory

Portal for Linux server inventory: live data synced from Zabbix (OS, CPU, RAM, uptime, vendor/model, monitoring status), plus vendor support end dates maintained by an admin.

## Стек

- Backend: Python FastAPI
- Frontend: Jinja2 + Bootstrap
- Database: PostgreSQL
- ORM: SQLAlchemy
- Migrations: Alembic
- Export: Excel через openpyxl
- Deployment: Docker Compose

## Быстрый запуск через Docker Compose

```bash
cp .env.example .env
# заполните ZABBIX_URL / ZABBIX_API_TOKEN в .env
docker compose up -d --build
```

Приложение будет доступно на `http://localhost:8000`.

## Интеграция с Zabbix

Данные тянутся из группы хостов Zabbix `Linux servers` (настраивается через `ZABBIX_HOST_GROUP`):

- **Живые данные из Zabbix**: hostname, IP, OS, CPU cores, RAM, uptime, vendor/model (через DMI item'ы `/sys/class/dmi/id/*`), статус мониторинга, количество проблем
- **Из тегов хоста в Zabbix** (`environment`, `datacenter`) — если тег не задан, поле показывается как `UNKNOWN`/`Unknown`
- **Только вручную через Admin**: support end date для физических серверов — этого нет в Zabbix

Синхронизация запускается автоматически (раз в `ZABBIX_AUTO_REFRESH_SECONDS`, по умолчанию 300 сек) при заходе на дашборд, либо вручную:

```bash
docker compose exec app ./sync_zabbix
```

Если Zabbix использует самоподписанный сертификат:

```bash
ZABBIX_VERIFY_SSL=false
```

или, правильнее, смонтируйте внутренний CA-сертификат и укажите путь в `ZABBIX_CA_FILE`.

Если контейнер не может разрешить имя Zabbix (ошибка вида `[Errno -5] No address associated with hostname` или `Temporary failure in name resolution`), хотя с хоста `getent hosts <имя>` резолвит нормально — это частая история с корпоративным DNS внутри Docker-сети. Пропишите статический IP:

```bash
# в .env
ZABBIX_HOSTNAME=zabbix.example.local
ZABBIX_IP=10.0.0.10
```

```bash
docker compose -f docker-compose.yml -f docker-compose.zabbix-host.yml up -d --build
docker compose -f docker-compose.yml -f docker-compose.zabbix-host.yml exec app ./sync_zabbix
```

## Локальный запуск без Docker

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

## Основные страницы

- `/?view=overview` — Overview
- `/?view=hosts` — список серверов с фильтрами
- `/hosts/{id}` — детали сервера
- `/admin/support` — редактирование support end date (нужен логин)
- `/exports/hosts.xlsx` — экспорт в Excel

## Модель данных

`hosts`: сервер + живые поля Zabbix (`zabbix_hostid`, `zabbix_host_name`, `zabbix_url`, `zabbix_agent_availability`, `monitoring_status`, `problem_count`, `zabbix_last_sync_at`, `os_name`, `cpu_cores`, `ram_gb`, `uptime_seconds`, `vendor`, `model`, `virtual`) + единственное ручное поле `support_end_date`.
