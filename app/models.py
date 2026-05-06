from datetime import date, datetime

from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_db


ROOM_PRICES = {
    "Стандарт": 4000,
    "Комфорт": 7000,
    "Люкс": 12000,
}

BOOKING_STATUSES = ("Новая", "Оплачено", "Отменено", "Прошедшее")
PAYMENT_METHODS = ("Оплата при заселении", "СБП", "Банковская карта")


def now_text():
    return datetime.now().isoformat(timespec="seconds")


def parse_date(value):
    return datetime.strptime(value, "%Y-%m-%d").date()


def calculate_booking(check_in, check_out, room_type, children):
    start = parse_date(check_in)
    end = parse_date(check_out)
    days = (end - start).days
    if days <= 0:
        raise ValueError("Дата выезда должна быть позже даты заезда.")
    if room_type not in ROOM_PRICES:
        raise ValueError("Выберите корректный тип номера.")
    price = ROOM_PRICES[room_type] * days + int(children) * 500 * days
    return days, price


def update_past_bookings(user_id=None):
    db = get_db()
    today = date.today().isoformat()
    if user_id is None:
        db.execute(
            """
            UPDATE bookings
            SET status = ?
            WHERE check_out < ? AND status NOT IN (?, ?)
            """,
            ("Прошедшее", today, "Отменено", "Прошедшее"),
        )
    else:
        db.execute(
            """
            UPDATE bookings
            SET status = ?
            WHERE user_id = ? AND check_out < ? AND status NOT IN (?, ?)
            """,
            ("Прошедшее", user_id, today, "Отменено", "Прошедшее"),
        )
    db.commit()


def create_user(data, role="user"):
    db = get_db()
    db.execute(
        """
        INSERT INTO users (
            surname, name, patronymic, email, phone, passport_series,
            passport_number, password_hash, role, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data["surname"].strip(),
            data["name"].strip(),
            data.get("patronymic", "").strip(),
            data["email"].strip().lower(),
            data["phone"].strip(),
            data["passport_series"].strip(),
            data["passport_number"].strip(),
            generate_password_hash(data["password"]),
            role,
            now_text(),
        ),
    )
    db.commit()


def get_user_by_login(login):
    login = login.strip().lower()
    return get_db().execute(
        "SELECT * FROM users WHERE lower(email) = ? OR phone = ?",
        (login, login),
    ).fetchone()


def get_user(user_id):
    return get_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def verify_user(login, password):
    user = get_user_by_login(login)
    if user and check_password_hash(user["password_hash"], password):
        return user
    return None


def update_user(user_id, data, password_hash=None):
    db = get_db()
    if password_hash:
        db.execute(
            """
            UPDATE users
            SET surname = ?, name = ?, patronymic = ?, email = ?, phone = ?,
                passport_series = ?, passport_number = ?, password_hash = ?
            WHERE id = ?
            """,
            (
                data["surname"].strip(),
                data["name"].strip(),
                data.get("patronymic", "").strip(),
                data["email"].strip().lower(),
                data["phone"].strip(),
                data["passport_series"].strip(),
                data["passport_number"].strip(),
                password_hash,
                user_id,
            ),
        )
    else:
        db.execute(
            """
            UPDATE users
            SET surname = ?, name = ?, patronymic = ?, email = ?, phone = ?,
                passport_series = ?, passport_number = ?
            WHERE id = ?
            """,
            (
                data["surname"].strip(),
                data["name"].strip(),
                data.get("patronymic", "").strip(),
                data["email"].strip().lower(),
                data["phone"].strip(),
                data["passport_series"].strip(),
                data["passport_number"].strip(),
                user_id,
            ),
        )
    db.commit()


def create_booking(user_id, data):
    adults = int(data.get("adults", 1))
    children = int(data.get("children", 0))
    if adults < 1 or children < 0:
        raise ValueError("Укажите корректное количество гостей.")
    days, price = calculate_booking(data["check_in"], data["check_out"], data["room_type"], children)

    db = get_db()
    db.execute(
        """
        INSERT INTO bookings (
            user_id, room_type, check_in, check_out, adults, children,
            days, price, status, payment_method, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            data["room_type"],
            data["check_in"],
            data["check_out"],
            adults,
            children,
            days,
            price,
            "Новая",
            None,
            now_text(),
        ),
    )
    db.commit()


def get_user_bookings(user_id):
    update_past_bookings(user_id)
    return get_db().execute(
        "SELECT * FROM bookings WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,),
    ).fetchall()


def get_booking_for_user(booking_id, user_id):
    return get_db().execute(
        "SELECT * FROM bookings WHERE id = ? AND user_id = ?",
        (booking_id, user_id),
    ).fetchone()


def get_booking(booking_id):
    return get_db().execute("SELECT * FROM bookings WHERE id = ?", (booking_id,)).fetchone()


def cancel_booking(booking_id, user_id):
    db = get_db()
    booking = get_booking_for_user(booking_id, user_id)
    if not booking:
        raise PermissionError("Бронирование не найдено или недоступно.")
    if booking["status"] == "Прошедшее":
        raise ValueError("Прошедшее бронирование нельзя отменить.")
    db.execute("UPDATE bookings SET status = ? WHERE id = ? AND user_id = ?", ("Отменено", booking_id, user_id))
    db.commit()


def pay_booking(booking, payment_method):
    if payment_method not in PAYMENT_METHODS:
        raise ValueError("Выберите корректный способ оплаты.")
    db = get_db()
    db.execute(
        "UPDATE bookings SET status = ?, payment_method = ? WHERE id = ?",
        ("Оплачено", payment_method, booking["id"]),
    )
    db.execute(
        """
        INSERT INTO payments (booking_id, payment_method, amount, status, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (booking["id"], payment_method, booking["price"], "Успешно", now_text()),
    )
    db.commit()


def all_users():
    return get_db().execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()


def all_bookings(status=None):
    update_past_bookings()
    if status:
        return get_db().execute(
            """
            SELECT b.*, u.surname, u.name, u.email
            FROM bookings b JOIN users u ON u.id = b.user_id
            WHERE b.status = ?
            ORDER BY b.created_at DESC
            """,
            (status,),
        ).fetchall()
    return get_db().execute(
        """
        SELECT b.*, u.surname, u.name, u.email
        FROM bookings b JOIN users u ON u.id = b.user_id
        ORDER BY b.created_at DESC
        """
    ).fetchall()


def admin_update_booking(booking_id, data):
    adults = int(data.get("adults", 1))
    children = int(data.get("children", 0))
    days, price = calculate_booking(data["check_in"], data["check_out"], data["room_type"], children)
    status = data.get("status", "Новая")
    if status not in BOOKING_STATUSES:
        raise ValueError("Некорректный статус бронирования.")
    db = get_db()
    db.execute(
        """
        UPDATE bookings
        SET room_type = ?, check_in = ?, check_out = ?, adults = ?, children = ?,
            days = ?, price = ?, status = ?, payment_method = ?
        WHERE id = ?
        """,
        (
            data["room_type"],
            data["check_in"],
            data["check_out"],
            adults,
            children,
            days,
            price,
            status,
            data.get("payment_method") or None,
            booking_id,
        ),
    )
    db.commit()


def admin_set_status(booking_id, status):
    if status not in BOOKING_STATUSES:
        raise ValueError("Некорректный статус бронирования.")
    db = get_db()
    db.execute("UPDATE bookings SET status = ? WHERE id = ?", (status, booking_id))
    db.commit()


def admin_delete_booking(booking_id):
    db = get_db()
    db.execute("DELETE FROM payments WHERE booking_id = ?", (booking_id,))
    db.execute("DELETE FROM bookings WHERE id = ?", (booking_id,))
    db.commit()
