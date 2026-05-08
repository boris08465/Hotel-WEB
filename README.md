# WSGI-приложение «Картотека бронирований гостиницы Космос»

## Запуск

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python wsgi.py
```

Приложение будет доступно по адресу `http://127.0.0.1:5000`.

## API

- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/admin/users`
- `GET /api/admin/bookings`
- `PUT /api/admin/bookings/<id>`
- `PATCH /api/admin/bookings/<id>/status`
- `DELETE /api/admin/bookings/<id>`
- `POST /api/admin/import`

## Администратор

При первом запуске автоматически создается администратор:

- email: `admin@cosmos.local`
- пароль: `admin12345`

Значения можно изменить через переменные окружения `ADMIN_EMAIL` и `ADMIN_PASSWORD` до первого запуска.

## Данные

SQLite-база создается автоматически в `data/database.sqlite`.
Импорт данных из предыдущей лабораторной выполняется в админ-панели из файла `data/import_data.pkl`.

## Консольный админ-клиент

Для работы из терминала через API:

```bash
python3 console_admin.py
```