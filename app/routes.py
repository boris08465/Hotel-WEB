import pickle
import sqlite3
from functools import wraps

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_db
from .models import (
    BOOKING_STATUSES,
    PAYMENT_METHODS,
    ROOM_PRICES,
    admin_delete_booking,
    admin_set_status,
    admin_update_booking,
    all_bookings,
    all_users,
    cancel_booking,
    create_booking,
    create_user,
    get_booking,
    get_booking_for_user,
    get_user,
    get_user_bookings,
    now_text,
    pay_booking,
    update_user,
    verify_user,
)

bp = Blueprint("main", __name__)


@bp.app_context_processor
def inject_user():
    user = get_user(session["user_id"]) if session.get("user_id") else None
    return {"current_user": user}


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Войдите в систему, чтобы продолжить.", "error")
            return redirect(url_for("main.login"))
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = get_user(session.get("user_id")) if session.get("user_id") else None
        if not user or user["role"] != "admin":
            flash("Административный раздел доступен только администратору.", "error")
            return redirect(url_for("main.index"))
        return view(*args, **kwargs)

    return wrapped


def required_fields(form, fields):
    missing = [label for name, label in fields if not form.get(name, "").strip()]
    if missing:
        return "Заполните обязательные поля: " + ", ".join(missing) + "."
    return None


@bp.route("/")
def index():
    return render_template("index.html")


@bp.route("/register", methods=("GET", "POST"))
def register():
    if request.method == "POST":
        error = required_fields(
            request.form,
            (
                ("surname", "фамилия"),
                ("name", "имя"),
                ("phone", "телефон"),
                ("email", "email"),
                ("passport_series", "серия паспорта"),
                ("passport_number", "номер паспорта"),
                ("password", "пароль"),
                ("password_confirm", "подтверждение пароля"),
            ),
        )
        if not error and request.form["password"] != request.form["password_confirm"]:
            error = "Пароль и подтверждение пароля не совпадают."
        if error:
            flash(error, "error")
            return render_template("register.html")

        try:
            create_user(request.form)
        except sqlite3.IntegrityError:
            flash("Пользователь с таким email уже зарегистрирован.", "error")
            return render_template("register.html")

        flash("Регистрация завершена. Теперь можно войти.", "success")
        return redirect(url_for("main.login"))
    return render_template("register.html")


@bp.route("/login", methods=("GET", "POST"))
def login():
    if request.method == "POST":
        user = verify_user(request.form.get("login", ""), request.form.get("password", ""))
        if not user:
            flash("Неверный логин или пароль.", "error")
            return render_template("login.html")
        session.clear()
        session["user_id"] = user["id"]
        flash("Вы вошли в личный кабинет.", "success")
        return redirect(url_for("main.profile"))
    return render_template("login.html")


@bp.route("/logout")
def logout():
    session.clear()
    flash("Вы вышли из системы.", "success")
    return redirect(url_for("main.index"))


@bp.route("/profile")
@login_required
def profile():
    return render_template("profile.html", user=get_user(session["user_id"]))


@bp.route("/settings", methods=("GET", "POST"))
@login_required
def settings():
    user = get_user(session["user_id"])
    if request.method == "POST":
        error = required_fields(
            request.form,
            (
                ("surname", "фамилия"),
                ("name", "имя"),
                ("phone", "телефон"),
                ("email", "email"),
                ("passport_series", "серия паспорта"),
                ("passport_number", "номер паспорта"),
            ),
        )
        password_hash = None
        new_password = request.form.get("password", "")
        if not error and new_password:
            if not check_password_hash(user["password_hash"], request.form.get("old_password", "")):
                error = "Для смены пароля укажите верный старый пароль."
            else:
                password_hash = generate_password_hash(new_password)
        if error:
            flash(error, "error")
            return render_template("settings.html", user=user)
        try:
            update_user(user["id"], request.form, password_hash)
        except sqlite3.IntegrityError:
            flash("Этот email уже используется другим пользователем.", "error")
            return render_template("settings.html", user=user)
        flash("Настройки профиля сохранены.", "success")
        return redirect(url_for("main.profile"))
    return render_template("settings.html", user=user)


@bp.route("/booking", methods=("GET", "POST"))
@login_required
def booking():
    if request.method == "POST":
        error = required_fields(
            request.form,
            (
                ("check_in", "дата заезда"),
                ("check_out", "дата выезда"),
                ("room_type", "тип номера"),
                ("adults", "взрослые гости"),
            ),
        )
        if error:
            flash(error, "error")
            return render_template("booking.html", room_prices=ROOM_PRICES)
        try:
            create_booking(session["user_id"], request.form)
        except ValueError as exc:
            flash(str(exc), "error")
            return render_template("booking.html", room_prices=ROOM_PRICES)
        flash("Бронирование создано.", "success")
        return redirect(url_for("main.my_bookings"))
    return render_template("booking.html", room_prices=ROOM_PRICES)


@bp.route("/my-bookings")
@login_required
def my_bookings():
    return render_template("my_bookings.html", bookings=get_user_bookings(session["user_id"]))


@bp.route("/booking/<int:booking_id>/cancel", methods=("POST",))
@login_required
def cancel(booking_id):
    try:
        cancel_booking(booking_id, session["user_id"])
        flash("Бронирование отменено.", "success")
    except (PermissionError, ValueError) as exc:
        flash(str(exc), "error")
    return redirect(url_for("main.my_bookings"))


@bp.route("/booking/<int:booking_id>/payment", methods=("GET", "POST"))
@login_required
def payment(booking_id):
    booking_item = get_booking_for_user(booking_id, session["user_id"])
    if not booking_item:
        flash("Бронирование не найдено или недоступно.", "error")
        return redirect(url_for("main.my_bookings"))
    if booking_item["status"] in ("Оплачено", "Отменено", "Прошедшее"):
        flash("Это бронирование нельзя оплатить.", "error")
        return redirect(url_for("main.my_bookings"))

    if request.method == "POST":
        method = request.form.get("payment_method", "")
        if method == "Банковская карта":
            error = required_fields(
                request.form,
                (
                    ("card_number", "номер карты"),
                    ("card_holder", "владелец карты"),
                    ("card_expiry", "срок действия"),
                    ("card_cvv", "CVV"),
                ),
            )
            if error:
                flash(error, "error")
                return render_template("payment.html", booking=booking_item, payment_methods=PAYMENT_METHODS)
        try:
            pay_booking(booking_item, method)
        except ValueError as exc:
            flash(str(exc), "error")
            return render_template("payment.html", booking=booking_item, payment_methods=PAYMENT_METHODS)
        flash("Оплата успешно зарегистрирована.", "success")
        return redirect(url_for("main.my_bookings"))
    return render_template("payment.html", booking=booking_item, payment_methods=PAYMENT_METHODS)


@bp.route("/admin")
@admin_required
def admin():
    return render_template("admin.html", bookings=all_bookings(), statuses=BOOKING_STATUSES)


@bp.route("/admin/users")
@admin_required
def admin_users():
    return render_template("admin_users.html", users=all_users())


@bp.route("/admin/bookings")
@admin_required
def admin_bookings():
    status = request.args.get("status") or None
    return render_template(
        "admin_bookings.html",
        bookings=all_bookings(status),
        statuses=BOOKING_STATUSES,
        room_prices=ROOM_PRICES,
        payment_methods=PAYMENT_METHODS,
        selected_status=status,
    )


@bp.route("/admin/booking/<int:booking_id>/edit", methods=("POST",))
@admin_required
def admin_booking_edit(booking_id):
    try:
        admin_update_booking(booking_id, request.form)
        flash("Бронирование обновлено.", "success")
    except ValueError as exc:
        flash(str(exc), "error")
    return redirect(url_for("main.admin_bookings"))


@bp.route("/admin/booking/<int:booking_id>/delete", methods=("POST",))
@admin_required
def admin_booking_delete(booking_id):
    admin_delete_booking(booking_id)
    flash("Бронирование удалено.", "success")
    return redirect(url_for("main.admin_bookings"))


@bp.route("/admin/booking/<int:booking_id>/status", methods=("POST",))
@admin_required
def admin_booking_status(booking_id):
    try:
        admin_set_status(booking_id, request.form.get("status", ""))
        flash("Статус бронирования изменен.", "success")
    except ValueError as exc:
        flash(str(exc), "error")
    return redirect(url_for("main.admin_bookings"))


@bp.route("/admin/import", methods=("POST",))
@admin_required
def admin_import():
    message, category = import_pickle_data()
    flash(message, category)
    return redirect(url_for("main.admin"))


def import_pickle_data():
    import_path = current_app.config["IMPORT_PATH"]
    if not import_path.exists():
        return "Файл data/import_data.pkl не найден.", "error"

    try:
        with import_path.open("rb") as fh:
            payload = pickle.load(fh)
    except (OSError, pickle.PickleError, EOFError, AttributeError, ImportError) as exc:
        return f"Не удалось прочитать файл импорта: {exc}", "error"

    users = _extract_collection(payload, "users", "пользователи")
    bookings = _extract_collection(payload, "bookings", "бронирования")

    db = get_db()
    imported_users = 0
    imported_bookings = 0
    email_to_id = {row["email"].lower(): row["id"] for row in db.execute("SELECT id, email FROM users")}

    for item in users:
        user = _as_dict(item)
        email = str(user.get("email", "")).strip().lower()
        if not email or email in email_to_id:
            continue
        password = str(user.get("password") or user.get("password_hash") or "123456")
        password_hash = password if password.startswith(("scrypt:", "pbkdf2:")) else generate_password_hash(password)
        db.execute(
            """
            INSERT INTO users (
                surname, name, patronymic, email, phone, passport_series,
                passport_number, password_hash, role, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(user.get("surname") or user.get("last_name") or "Фамилия"),
                str(user.get("name") or user.get("first_name") or "Имя"),
                str(user.get("patronymic") or user.get("middle_name") or ""),
                email,
                str(user.get("phone") or "+70000000000"),
                str(user.get("passport_series") or user.get("passport_seria") or "0000"),
                str(user.get("passport_number") or "000000"),
                password_hash,
                str(user.get("role") or "user"),
                str(user.get("created_at") or now_text()),
            ),
        )
        email_to_id[email] = db.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
        imported_users += 1

    for item in bookings:
        booking = _as_dict(item)
        user_id = _resolve_import_user_id(booking, email_to_id)
        if not user_id:
            continue
        room_type = str(booking.get("room_type") or booking.get("room") or "Стандарт")
        check_in = str(booking.get("check_in") or booking.get("arrival_date") or "")
        check_out = str(booking.get("check_out") or booking.get("departure_date") or "")
        if _booking_exists(db, user_id, room_type, check_in, check_out):
            continue
        try:
            adults = int(booking.get("adults") or 1)
            children = int(booking.get("children") or 0)
            days = int(booking.get("days") or 1)
            price = int(booking.get("price") or ROOM_PRICES.get(room_type, 4000) * days)
        except (TypeError, ValueError):
            continue
        db.execute(
            """
            INSERT INTO bookings (
                user_id, room_type, check_in, check_out, adults, children,
                days, price, status, payment_method, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                room_type,
                check_in,
                check_out,
                adults,
                children,
                days,
                price,
                str(booking.get("status") or "Новая"),
                booking.get("payment_method"),
                str(booking.get("created_at") or now_text()),
            ),
        )
        imported_bookings += 1

    db.commit()
    return f"Импорт завершен: пользователей {imported_users}, бронирований {imported_bookings}.", "success"


def _extract_collection(payload, *names):
    if isinstance(payload, dict):
        for name in names:
            value = payload.get(name)
            if isinstance(value, (list, tuple)):
                return value
    for name in names:
        value = getattr(payload, name, None)
        if isinstance(value, (list, tuple)):
            return value
    return []


def _as_dict(item):
    if isinstance(item, dict):
        return item
    return {
        key: value
        for key, value in vars(item).items()
        if not key.startswith("_")
    }


def _resolve_import_user_id(booking, email_to_id):
    email = str(booking.get("email") or booking.get("user_email") or "").strip().lower()
    if email and email in email_to_id:
        return email_to_id[email]
    try:
        return int(booking.get("user_id") or 0)
    except (TypeError, ValueError):
        return None


def _booking_exists(db, user_id, room_type, check_in, check_out):
    return db.execute(
        """
        SELECT id FROM bookings
        WHERE user_id = ? AND room_type = ? AND check_in = ? AND check_out = ?
        """,
        (user_id, room_type, check_in, check_out),
    ).fetchone()
