import pickle
from functools import wraps

from flask_login import current_user, login_required, login_user, logout_user
from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from werkzeug.security import generate_password_hash

from .db import get_db
from . import csrf
from .forms import (
    AdminBookingEditForm,
    AdminBookingStatusForm,
    AdminImportForm,
    BookingForm,
    CancelBookingForm,
    LoginForm,
    PaymentForm,
    RegisterForm,
    SettingsForm,
)
from .models import (
    BOOKING_STATUSES,
    LoginUser,
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


def flash_form_errors(form):
    for errors in form.errors.values():
        for error in errors:
            flash(error, "error")


def _row_to_dict(row):
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}


def api_login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({"error": "auth_required"}), 401
        return view(*args, **kwargs)

    return wrapped


def api_admin_required(view):
    @wraps(view)
    @api_login_required
    def wrapped(*args, **kwargs):
        if current_user.role != "admin":
            return jsonify({"error": "admin_required"}), 403
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != "admin":
            flash("Административный раздел доступен только администратору.", "error")
            return redirect(url_for("main.index"))
        return view(*args, **kwargs)

    return wrapped


@bp.route("/")
def index():
    return render_template("index.html")


@bp.route("/api/auth/login", methods=("POST",))
@csrf.exempt
def api_login():
    payload = request.get_json(silent=True) or {}
    login_value = str(payload.get("login", "")).strip()
    password = str(payload.get("password", ""))
    user = verify_user(login_value, password)
    if not user:
        return jsonify({"error": "invalid_credentials"}), 401
    login_user(LoginUser(user))
    return jsonify({"ok": True, "user": {"id": user["id"], "name": user["name"], "role": user["role"]}})


@bp.route("/api/auth/logout", methods=("POST",))
@csrf.exempt
@api_login_required
def api_logout():
    logout_user()
    return jsonify({"ok": True})


@bp.route("/api/admin/users", methods=("GET",))
@api_admin_required
def api_admin_users():
    return jsonify({"items": [_row_to_dict(item) for item in all_users()]})


@bp.route("/api/admin/bookings", methods=("GET",))
@api_admin_required
def api_admin_bookings():
    status = request.args.get("status") or None
    return jsonify({"items": [_row_to_dict(item) for item in all_bookings(status)]})


@bp.route("/api/admin/bookings/<int:booking_id>", methods=("PUT",))
@csrf.exempt
@api_admin_required
def api_admin_booking_edit(booking_id):
    payload = request.get_json(silent=True) or {}
    try:
        normalized = {
            "check_in": str(payload.get("check_in", "")),
            "check_out": str(payload.get("check_out", "")),
            "adults": int(payload.get("adults", 1)),
            "children": int(payload.get("children", 0)),
            "room_type": str(payload.get("room_type", "")),
            "status": str(payload.get("status", "")),
            "payment_method": payload.get("payment_method") or None,
        }
    except (TypeError, ValueError):
        return jsonify({"error": "invalid_payload"}), 400
    try:
        admin_update_booking(booking_id, normalized)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"ok": True, "booking": _row_to_dict(get_booking(booking_id))})


@bp.route("/api/admin/bookings/<int:booking_id>/status", methods=("PATCH",))
@csrf.exempt
@api_admin_required
def api_admin_booking_status(booking_id):
    payload = request.get_json(silent=True) or {}
    status = str(payload.get("status", ""))
    try:
        admin_set_status(booking_id, status)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"ok": True, "booking": _row_to_dict(get_booking(booking_id))})


@bp.route("/api/admin/bookings/<int:booking_id>", methods=("DELETE",))
@csrf.exempt
@api_admin_required
def api_admin_booking_delete(booking_id):
    admin_delete_booking(booking_id)
    return jsonify({"ok": True})


@bp.route("/api/admin/import", methods=("POST",))
@csrf.exempt
@api_admin_required
def api_admin_import():
    message, category = import_pickle_data()
    ok = category == "success"
    status = 200 if ok else 400
    return jsonify({"ok": ok, "category": category, "message": message}), status


@bp.route("/register", methods=("GET", "POST"))
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        create_user(form.data)
        flash("Регистрация завершена. Теперь можно войти.", "success")
        return redirect(url_for("main.login"))
    if form.is_submitted() and form.errors:
        flash("Проверьте корректность заполнения формы.", "error")
    return render_template("register.html", form=form)


@bp.route("/login", methods=("GET", "POST"))
def login():
    form = LoginForm()
    if form.validate_on_submit():
        login_user(LoginUser(form.user))
        flash("Вы вошли в личный кабинет.", "success")
        return redirect(url_for("main.profile"))
    if form.is_submitted() and form.errors:
        flash("Проверьте корректность заполнения формы.", "error")
    return render_template("login.html", form=form)


@bp.route("/logout")
def logout():
    logout_user()
    flash("Вы вышли из системы.", "success")
    return redirect(url_for("main.index"))


@bp.route("/profile")
@login_required
def profile():
    return render_template("profile.html", user=get_user(current_user.id))


@bp.route("/settings", methods=("GET", "POST"))
@login_required
def settings():
    user = get_user(current_user.id)
    form = SettingsForm(data=user)
    form.current_user_id = current_user.id
    form.current_password_hash = user["password_hash"]
    if form.validate_on_submit():
        password_hash = None
        if form.password.data:
            password_hash = generate_password_hash(form.password.data)
        update_user(user["id"], form.data, password_hash)
        flash("Настройки профиля сохранены.", "success")
        return redirect(url_for("main.profile"))
    if form.is_submitted() and form.errors:
        flash("Проверьте корректность заполнения формы.", "error")
    return render_template("settings.html", user=user, form=form)


@bp.route("/booking", methods=("GET", "POST"))
@login_required
def booking():
    form = BookingForm()
    if form.validate_on_submit():
        try:
            payload = {
                "check_in": form.check_in.data.isoformat(),
                "check_out": form.check_out.data.isoformat(),
                "room_type": form.room_type.data,
                "adults": form.adults.data,
                "children": form.children.data or 0,
            }
            create_booking(current_user.id, payload)
        except ValueError as exc:
            flash(str(exc), "error")
            return render_template("booking.html", room_prices=ROOM_PRICES, form=form)
        flash("Бронирование создано.", "success")
        return redirect(url_for("main.my_bookings"))
    if form.is_submitted() and form.errors:
        flash("Проверьте корректность заполнения формы.", "error")
    return render_template("booking.html", room_prices=ROOM_PRICES, form=form)


@bp.route("/my-bookings")
@login_required
def my_bookings():
    return render_template("my_bookings.html", bookings=get_user_bookings(current_user.id))


@bp.route("/booking/<int:booking_id>/cancel", methods=("POST",))
@login_required
def cancel(booking_id):
    form = CancelBookingForm()
    if not form.validate_on_submit():
        flash_form_errors(form)
        return redirect(url_for("main.my_bookings"))
    try:
        cancel_booking(booking_id, current_user.id)
        flash("Бронирование отменено.", "success")
    except (PermissionError, ValueError) as exc:
        flash(str(exc), "error")
    return redirect(url_for("main.my_bookings"))


@bp.route("/booking/<int:booking_id>/payment", methods=("GET", "POST"))
@login_required
def payment(booking_id):
    booking_item = get_booking_for_user(booking_id, current_user.id)
    if not booking_item:
        flash("Бронирование не найдено или недоступно.", "error")
        return redirect(url_for("main.my_bookings"))
    if booking_item["status"] in ("Оплачено", "Отменено", "Прошедшее"):
        flash("Это бронирование нельзя оплатить.", "error")
        return redirect(url_for("main.my_bookings"))

    form = PaymentForm()
    if form.validate_on_submit():
        method = form.payment_method.data
        try:
            pay_booking(booking_item, method)
        except ValueError as exc:
            flash(str(exc), "error")
            return render_template("payment.html", booking=booking_item, payment_methods=PAYMENT_METHODS, form=form)
        flash("Оплата успешно зарегистрирована.", "success")
        return redirect(url_for("main.my_bookings"))
    if form.is_submitted() and form.errors:
        flash("Проверьте корректность заполнения формы.", "error")
    return render_template("payment.html", booking=booking_item, payment_methods=PAYMENT_METHODS, form=form)


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
    form = AdminBookingEditForm()
    if not form.validate_on_submit():
        flash_form_errors(form)
        return redirect(url_for("main.admin_bookings"))
    try:
        payload = {
            "check_in": form.check_in.data.isoformat(),
            "check_out": form.check_out.data.isoformat(),
            "adults": form.adults.data,
            "children": form.children.data,
            "room_type": form.room_type.data,
            "status": form.status.data,
            "payment_method": form.payment_method.data,
        }
        admin_update_booking(booking_id, payload)
        flash("Бронирование обновлено.", "success")
    except ValueError as exc:
        flash(str(exc), "error")
    return redirect(url_for("main.admin_bookings"))


@bp.route("/admin/booking/<int:booking_id>/delete", methods=("POST",))
@admin_required
def admin_booking_delete(booking_id):
    form = CancelBookingForm()
    if not form.validate_on_submit():
        flash_form_errors(form)
        return redirect(url_for("main.admin_bookings"))
    admin_delete_booking(booking_id)
    flash("Бронирование удалено.", "success")
    return redirect(url_for("main.admin_bookings"))


@bp.route("/admin/booking/<int:booking_id>/status", methods=("POST",))
@admin_required
def admin_booking_status(booking_id):
    form = AdminBookingStatusForm()
    if not form.validate_on_submit():
        flash_form_errors(form)
        return redirect(url_for("main.admin_bookings"))
    try:
        admin_set_status(booking_id, form.status.data)
        flash("Статус бронирования изменен.", "success")
    except ValueError as exc:
        flash(str(exc), "error")
    return redirect(url_for("main.admin_bookings"))


@bp.route("/admin/import", methods=("POST",))
@admin_required
def admin_import():
    form = AdminImportForm()
    if not form.validate_on_submit():
        flash_form_errors(form)
        return redirect(url_for("main.admin"))
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
