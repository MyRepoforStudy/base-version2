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
- `/?view=hosts` — инвентарный список серверов с фильтрами
- `/?view=performance` — CPU, RAM, filesystem capacity, uptime и Health Score
- `/?view=capacity` — прогноз заполнения дисков, Availability и SLA за 30 дней
- `/hosts/{id}` — детали сервера
- `/admin/support` — редактирование support end date (нужен логин)
- `/admin/ownership` — владельцы, сервисы и criticality (нужен логин)
- `/exports/hosts.xlsx` — экспорт в Excel

## Модель данных

`hosts`: сервер + живые поля Zabbix (`zabbix_hostid`, `zabbix_host_name`, `zabbix_url`, `zabbix_agent_availability`, `monitoring_status`, `problem_count`, `zabbix_last_sync_at`, `os_name`, `cpu_cores`, `ram_gb`, `uptime_seconds`, `vendor`, `model`, `virtual`) + ручные поля поддержки и ответственности.

## Uptime, OS Lifecycle и ответственные

Uptime поступает из стандартного Zabbix item `system.uptime`. Портал показывает
его длительность и вычисляет дату последней перезагрузки относительно времени
последней синхронизации Zabbix.

### Health, производительность и диски

Портал читает актуальные метрики из стандартных Zabbix items:

- CPU: `system.cpu.util` или `system.cpu.util[,idle]`;
- RAM: `vm.memory.utilization`, `vm.memory.size[pavailable]`,
  `vm.memory.size[pused]` или расчёт из `total + available`;
- load average: `system.cpu.load[all,avg1]`;
- файловые системы: семейство `vfs.fs.size[<mount>,total|used|pused]`
  (также поддерживаются dependent-item варианты). В списке серверов показывается
  самый заполненный раздел, а в карточке сервера — все обнаруженные mount points.

Server Health Score рассчитывается от 0 до 100 на основе доступности мониторинга,
активных проблем Zabbix, загрузки CPU/RAM, заполнения корневого раздела и статуса
OS Lifecycle. Отсутствующие метрики отображаются как `Unknown` и не подменяются
случайными значениями.

Change History начинает накапливаться после установки этой версии. В неё входят
изменения инвентаря при синхронизации Zabbix и ручные изменения на страницах
администрирования. Быстро меняющиеся показатели CPU, RAM, disk и uptime в журнал
не записываются.

### Capacity Forecast и Availability SLA

При синхронизации Zabbix портал сохраняет исторический снимок раз в час и сразу
при изменении статуса мониторинга. Повторяющиеся данные хранятся 90 дней.
В Docker-контейнере фоновая синхронизация запускается каждые 5 минут независимо
от посещения портала; интервал задаётся через `ZABBIX_COLLECT_INTERVAL_SECONDS`.

- Capacity Forecast использует линейный тренд самого заполненного filesystem и
  прогнозирует дату достижения порога 95%. Для расчёта нужно минимум 6 точек за
  период не менее 24 часов.
- Availability рассчитывается по времени состояний `ok`/`problem` относительно
  всех подтверждённых интервалов за 30 дней.
- SLA по умолчанию равен 99.9%. Пока история не покрывает 95% расчётного окна,
  результат помечается как `Collecting`.

Интервал, retention, SLA и порог capacity настраиваются переменными
`METRIC_HISTORY_INTERVAL_SECONDS`, `METRIC_HISTORY_RETENTION_DAYS`,
`SLA_TARGET_PERCENT` и `CAPACITY_FORECAST_TARGET_PERCENT`.

При первой синхронизации портал загружает до 30 дней почасовых trends из
Zabbix: `vfs.fs.size[...,pused]` для Capacity Forecast и `agent.ping`
(с fallback на `icmpping`) для Availability. Глубина начальной загрузки
настраивается через `ZABBIX_HISTORY_BACKFILL_DAYS`.

Ответственные читаются из Zabbix host tags:

- owner: `owner`, `technical_owner`, `service_owner`;
- department: `department`, `business_unit`, `team`;
- business service: `service`, `business_service`, `application`;
- criticality: `criticality`, `importance`, `tier`.

Criticality поддерживает `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, а также `P1`–`P4`
и `tier-0`–`tier-3`. Администратор может заполнить или исправить значения на
`/admin/ownership`. Непустой tag Zabbix снова станет источником истины при
следующей синхронизации.

Семейство ОС, версия и окончание Standard/Premier support определяются по
названию ОС. Для купленной расширенной поддержки задайте host tag
`os_support_end`, `os_eol` или `os_eos` с ISO-датой, например `2032-05-31`.
