import re

from flask_wtf import FlaskForm
from wtforms import IntegerField, PasswordField, RadioField, SelectField, StringField, SubmitField
from wtforms.fields import DateField, EmailField
from wtforms.validators import DataRequired, Email, EqualTo, Length, NumberRange, Optional, Regexp, ValidationError
from werkzeug.security import check_password_hash

from .db import get_db
from .models import BOOKING_STATUSES, PAYMENT_METHODS, ROOM_PRICES, verify_user


class LoginForm(FlaskForm):
    login = StringField("Почта/номер телефона", validators=[DataRequired()])
    password = PasswordField("Пароль", validators=[DataRequired()])
    submit = SubmitField("Войти")

    def validate(self, extra_validators=None):
        is_valid = super().validate(extra_validators=extra_validators)
        if not is_valid:
            return False
        user = verify_user(self.login.data, self.password.data)
        if not user:
            self.login.errors.append("Неверный логин или пароль.")
            return False
        self.user = user
        return True


class RegisterForm(FlaskForm):
    name = StringField("Имя", validators=[DataRequired(), Length(min=2, max=50)])
    surname = StringField("Фамилия", validators=[DataRequired(), Length(min=2, max=50)])
    patronymic = StringField("Отчество", validators=[Optional(), Length(max=50)])
    phone = StringField(
        "Номер телефона",
        validators=[
            DataRequired(),
            Regexp(r"^\+?\d{10,15}$", message="Телефон должен содержать от 10 до 15 цифр (можно с +)."),
        ],
    )
    email = EmailField("Почта", validators=[DataRequired(), Email()])
    passport_number = StringField(
        "Номер паспорта",
        validators=[DataRequired(), Regexp(r"^\d{6}$", message="Номер паспорта должен содержать 6 цифр.")],
    )
    passport_series = StringField(
        "Серия паспорта",
        validators=[DataRequired(), Regexp(r"^\d{4}$", message="Серия паспорта должна содержать 4 цифры.")],
    )
    password = PasswordField("Пароль", validators=[DataRequired(), Length(min=8, message="Минимум 8 символов.")])
    password_confirm = PasswordField(
        "Подтверждение пароля",
        validators=[DataRequired(), EqualTo("password", message="Пароли должны совпадать.")],
    )
    submit = SubmitField("Создать аккаунт")

    def validate_email(self, field):
        exists = get_db().execute(
            "SELECT 1 FROM users WHERE lower(email) = ?",
            (field.data.strip().lower(),),
        ).fetchone()
        if exists:
            raise ValidationError("Пользователь с таким email уже зарегистрирован.")


class SettingsForm(FlaskForm):
    name = StringField("Имя", validators=[DataRequired(), Length(min=2, max=50)])
    surname = StringField("Фамилия", validators=[DataRequired(), Length(min=2, max=50)])
    patronymic = StringField("Отчество", validators=[Optional(), Length(max=50)])
    phone = StringField(
        "Номер телефона",
        validators=[
            DataRequired(),
            Regexp(r"^\+?\d{10,15}$", message="Телефон должен содержать от 10 до 15 цифр (можно с +)."),
        ],
    )
    email = EmailField("Почта", validators=[DataRequired(), Email()])
    passport_number = StringField(
        "Номер паспорта",
        validators=[DataRequired(), Regexp(r"^\d{6}$", message="Номер паспорта должен содержать 6 цифр.")],
    )
    passport_series = StringField(
        "Серия паспорта",
        validators=[DataRequired(), Regexp(r"^\d{4}$", message="Серия паспорта должна содержать 4 цифры.")],
    )
    old_password = PasswordField("Старый пароль", validators=[Optional()])
    password = PasswordField("Новый пароль", validators=[Optional(), Length(min=8, message="Минимум 8 символов.")])
    password_confirm = PasswordField(
        "Подтверждение нового пароля",
        validators=[Optional(), EqualTo("password", message="Новый пароль и подтверждение не совпадают.")],
    )
    submit = SubmitField("Сохранить")

    def validate(self, extra_validators=None):
        is_valid = super().validate(extra_validators=extra_validators)
        if not is_valid:
            return False
        if self.password.data:
            if not self.old_password.data:
                self.old_password.errors.append("Укажите старый пароль.")
                return False
            if not check_password_hash(self.current_password_hash, self.old_password.data):
                self.old_password.errors.append("Старый пароль указан неверно.")
                return False
        return True

    def validate_email(self, field):
        exists = get_db().execute(
            "SELECT id FROM users WHERE lower(email) = ? AND id != ?",
            (field.data.strip().lower(), self.current_user_id),
        ).fetchone()
        if exists:
            raise ValidationError("Этот email уже используется другим пользователем.")


class BookingForm(FlaskForm):
    room_type = RadioField(
        "Тип номера",
        choices=[(room_type, room_type) for room_type in ROOM_PRICES],
        validators=[DataRequired()],
    )
    check_in = DateField("Дата заезда", format="%Y-%m-%d", validators=[DataRequired()])
    check_out = DateField("Дата выезда", format="%Y-%m-%d", validators=[DataRequired()])
    adults = IntegerField("Количество взрослых гостей", validators=[DataRequired(), NumberRange(min=1)])
    children = IntegerField("Количество детей", validators=[Optional(), NumberRange(min=0)], default=0)
    submit = SubmitField("Забронировать")

    def validate_check_out(self, field):
        if self.check_in.data and field.data and field.data <= self.check_in.data:
            raise ValidationError("Дата выезда должна быть позже даты заезда.")


class PaymentForm(FlaskForm):
    payment_method = SelectField(
        "Способ оплаты",
        choices=[(method, method) for method in PAYMENT_METHODS],
        validators=[DataRequired()],
    )
    card_number = StringField("Номер карты", validators=[Optional(), Length(max=23)])
    card_holder = StringField("Владелец карты", validators=[Optional(), Length(min=2, max=100)])
    card_expiry = StringField("Срок действия", validators=[Optional(), Length(max=5)])
    card_cvv = StringField("CVV", validators=[Optional(), Length(max=4)])
    submit = SubmitField("Оплатить бронирование")

    def validate(self, extra_validators=None):
        is_valid = super().validate(extra_validators=extra_validators)
        if not is_valid:
            return False
        if self.payment_method.data == "Банковская карта":
            required = (
                (self.card_number, "Укажите номер карты."),
                (self.card_holder, "Укажите владельца карты."),
                (self.card_expiry, "Укажите срок действия карты."),
                (self.card_cvv, "Укажите CVV."),
            )
            has_errors = False
            for field, message in required:
                if not (field.data or "").strip():
                    field.errors.append(message)
                    has_errors = True
            if self.card_number.data and not re.fullmatch(r"\d{16,19}", self.card_number.data.replace(" ", "")):
                self.card_number.errors.append("Номер карты должен содержать 16-19 цифр.")
                has_errors = True
            if self.card_expiry.data and not re.fullmatch(r"(0[1-9]|1[0-2])\/\d{2}", self.card_expiry.data):
                self.card_expiry.errors.append("Срок действия должен быть в формате MM/YY.")
                has_errors = True
            if self.card_cvv.data and not re.fullmatch(r"\d{3,4}", self.card_cvv.data):
                self.card_cvv.errors.append("CVV должен содержать 3 или 4 цифры.")
                has_errors = True
            if has_errors:
                return False
        return True


class CancelBookingForm(FlaskForm):
    submit = SubmitField("Отменить бронирование")


class AdminImportForm(FlaskForm):
    submit = SubmitField("Импортировать")


class AdminExportForm(FlaskForm):
    submit = SubmitField("Save")


class AdminCreateBookingForm(FlaskForm):
    user_id = IntegerField("ID пользователя", validators=[DataRequired(), NumberRange(min=1)])
    room_type = SelectField(
        "Номер",
        choices=[(room_type, room_type) for room_type in ROOM_PRICES],
        validators=[DataRequired()],
    )
    check_in = DateField("Заезд", format="%Y-%m-%d", validators=[DataRequired()])
    check_out = DateField("Выезд", format="%Y-%m-%d", validators=[DataRequired()])
    adults = IntegerField("Взрослые", validators=[DataRequired(), NumberRange(min=1)])
    children = IntegerField("Дети", validators=[DataRequired(), NumberRange(min=0)])
    status = SelectField("Статус", validators=[DataRequired()])
    payment_method = SelectField("Способ оплаты", validators=[Optional()])
    submit = SubmitField("Создать бронирование")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.status.choices = [(status, status) for status in BOOKING_STATUSES]
        self.payment_method.choices = [("", "Не выбрано")] + [(method, method) for method in PAYMENT_METHODS]

    def validate_check_out(self, field):
        if self.check_in.data and field.data and field.data <= self.check_in.data:
            raise ValidationError("Дата выезда должна быть позже даты заезда.")

    def validate_user_id(self, field):
        exists = get_db().execute("SELECT 1 FROM users WHERE id = ?", (field.data,)).fetchone()
        if not exists:
            raise ValidationError("Пользователь с таким ID не найден.")


class AdminBookingStatusForm(FlaskForm):
    status = SelectField(
        "Статус",
        choices=[(status, status) for status in BOOKING_STATUSES],
        validators=[DataRequired()],
    )
    submit = SubmitField("Сменить статус")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.status.choices = [(status, status) for status in BOOKING_STATUSES]


class AdminBookingEditForm(FlaskForm):
    check_in = DateField("Заезд", format="%Y-%m-%d", validators=[DataRequired()])
    check_out = DateField("Выезд", format="%Y-%m-%d", validators=[DataRequired()])
    adults = IntegerField("Взрослые", validators=[DataRequired(), NumberRange(min=1)])
    children = IntegerField("Дети", validators=[DataRequired(), NumberRange(min=0)])
    room_type = SelectField(
        "Номер",
        choices=[(room_type, room_type) for room_type in ROOM_PRICES],
        validators=[DataRequired()],
    )
    status = SelectField("Статус", validators=[DataRequired()])
    payment_method = SelectField("Способ оплаты", validators=[Optional()])
    submit = SubmitField("Сохранить")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.status.choices = [(status, status) for status in BOOKING_STATUSES]
        self.payment_method.choices = [("", "Не выбрано")] + [(method, method) for method in PAYMENT_METHODS]

    def validate_check_out(self, field):
        if self.check_in.data and field.data and field.data <= self.check_in.data:
            raise ValidationError("Дата выезда должна быть позже даты заезда.")
