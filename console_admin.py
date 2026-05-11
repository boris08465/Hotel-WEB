import os
import sys

import requests


BASE_URL = os.environ.get("HOTEL_API_URL", "http://127.0.0.1:5000").rstrip("/")

ROOM_TYPES = {"1": "Стандарт", "2": "Комфорт", "3": "Люкс"}
PAYMENT_METHODS = {"1": "Банковская карта", "2": "СБП", "3": "Оплата при заселении"}
STATUSES = {"1": "Новая", "2": "Оплачено", "3": "Отменено", "4": "Прошедшее"}


class ConsoleSystem:
    def __init__(self, base_url):
        self.base_url = base_url
        self.session = requests.Session()
        self.current_user = None
        self.is_admin = False

    def _request(self, method, path, **kwargs):
        url = f"{self.base_url}{path}"
        try:
            response = self.session.request(method, url, timeout=15, **kwargs)
        except requests.RequestException as exc:
            print(f"Ошибка соединения: {exc}")
            return None, None
        try:
            payload = response.json()
        except ValueError:
            payload = None
        return response, payload

    def register(self):
        print("\n=== Регистрация ===")
        password = input("Пароль: ").strip()
        payload = {
            "surname": input("Фамилия: ").strip(),
            "name": input("Имя: ").strip(),
            "patronymic": input("Отчество: ").strip(),
            "email": input("Почта: ").strip(),
            "phone": input("Телефон: ").strip(),
            "passport_series": input("Серия паспорта: ").strip(),
            "passport_number": input("Номер паспорта: ").strip(),
            "password": password,
            "password_confirm": input("Подтверждение пароля: ").strip(),
        }
        response, data = self._request("POST", "/api/auth/register", json=payload)
        if response and response.status_code == 201:
            print("Регистрация успешна")
            return
        msg = data.get("error") if data else "unknown"
        print(f"Ошибка регистрации: {msg}")

    def login_user(self):
        print("\n=== Вход пользователя ===")
        login = input("Почта/телефон: ").strip()
        password = input("Пароль: ").strip()
        response, data = self._request("POST", "/api/auth/login", json={"login": login, "password": password})
        if response and response.status_code == 200 and data.get("user", {}).get("role") == "user":
            self.current_user = data["user"]
            self.is_admin = False
            print("Вы вошли как пользователь")
            return
        print("Ошибка входа")

    def login_admin(self):
        print("\n=== Вход администратора ===")
        login = input("Логин (email/телефон): ").strip()
        password = input("Пароль: ").strip()
        response, data = self._request("POST", "/api/auth/login", json={"login": login, "password": password})
        if response and response.status_code == 200 and data.get("user", {}).get("role") == "admin":
            self.current_user = data["user"]
            self.is_admin = True
            print("Вы вошли как администратор")
            return
        print("Ошибка входа администратора")

    def logout(self):
        self._request("POST", "/api/auth/logout", json={})
        self.current_user = None
        self.is_admin = False
        print("Вы вышли")

    def add_booking(self):
        if not self.current_user or self.is_admin:
            print("Сначала войдите как пользователь")
            return
        print("\nТип номера:")
        print("1. Стандарт")
        print("2. Комфорт")
        print("3. Люкс")
        choice = input("Выбор: ").strip()
        room_type = ROOM_TYPES.get(choice)
        if not room_type:
            print("Ошибка выбора типа номера")
            return
        check_in = input("Дата заезда (гггг-мм-дд): ").strip()
        check_out = input("Дата выезда (гггг-мм-дд): ").strip()
        try:
            adults = int(input("Количество взрослых: ").strip())
            children = int(input("Количество детей: ").strip())
        except ValueError:
            print("Ошибка: количество гостей должно быть числом")
            return
        payload = {
            "room_type": room_type,
            "check_in": check_in,
            "check_out": check_out,
            "adults": adults,
            "children": children,
        }
        response, data = self._request("POST", "/api/bookings", json=payload)
        if response and response.status_code == 201:
            print("Бронирование добавлено")
            return
        print(f"Ошибка: {data.get('error') if data else 'unknown'}")

    def show_my(self):
        if not self.current_user or self.is_admin:
            print("Сначала войдите как пользователь")
            return
        response, data = self._request("GET", "/api/bookings")
        if not response or response.status_code != 200:
            print("Не удалось получить бронирования")
            return
        items = data.get("items", [])
        print("\n=== Мои бронирования ===")
        if not items:
            print("У вас пока нет бронирований")
            return
        for item in items:
            print(
                f"[{item['id']}] {item['room_type']} | {item['check_in']} - {item['check_out']} | "
                f"Дней: {item['days']} | Взрослые: {item['adults']} | Дети: {item['children']} | "
                f"{item['status']} | {item['price']} руб. | Оплата: {item['payment_method'] or 'Не выбрано'}"
            )

    def pay_booking(self):
        if not self.current_user or self.is_admin:
            print("Сначала войдите как пользователь")
            return
        try:
            booking_id = int(input("ID брони: ").strip())
        except ValueError:
            print("Ошибка ввода ID")
            return
        print("Способ оплаты:")
        print("1. Карта")
        print("2. СБП")
        print("3. При заселении")
        method = PAYMENT_METHODS.get(input("Выбор: ").strip())
        if not method:
            print("Ошибка выбора способа оплаты")
            return
        response, data = self._request("POST", f"/api/bookings/{booking_id}/pay", json={"payment_method": method})
        if response and response.status_code == 200:
            print("Оплата успешна")
            return
        print(f"Ошибка оплаты: {data.get('error') if data else 'unknown'}")

    def admin_show_all_bookings(self):
        if not self.is_admin:
            print("Доступ только для администратора")
            return
        response, data = self._request("GET", "/api/admin/bookings")
        if not response or response.status_code != 200:
            print("Не удалось получить бронирования")
            return
        print("\n=== Все бронирования ===")
        items = data.get("items", [])
        if not items:
            print("Список бронирований пуст")
            return
        for item in items:
            print(
                f"[{item['id']}] {item['room_type']} | {item['check_in']} - {item['check_out']} | "
                f"Дней: {item['days']} | Взрослые: {item['adults']} | Дети: {item['children']} | "
                f"{item['status']} | {item['price']} руб. | Оплата: {item['payment_method'] or 'Не выбрано'}"
            )

    def admin_show_all_users(self):
        if not self.is_admin:
            print("Доступ только для администратора")
            return
        response, data = self._request("GET", "/api/admin/users")
        if not response or response.status_code != 200:
            print("Не удалось получить пользователей")
            return
        print("\n=== Все пользователи ===")
        items = data.get("items", [])
        if not items:
            print("Список пользователей пуст")
            return
        for user in items:
            print(f"[{user['id']}] {user['surname']} {user['name']} {user.get('patronymic') or ''} | {user['email']} | {user['phone']}")

    def edit_booking(self):
        if not self.is_admin:
            print("Редактировать бронирования может только администратор")
            return
        try:
            booking_id = int(input("ID брони: ").strip())
            adults = int(input("Новое количество взрослых: ").strip())
            children = int(input("Новое количество детей: ").strip())
        except ValueError:
            print("Ошибка ввода")
            return
        check_in = input("Новая дата заезда (гггг-мм-дд): ").strip()
        check_out = input("Новая дата выезда (гггг-мм-дд): ").strip()
        print("Тип номера: 1.Стандарт 2.Комфорт 3.Люкс")
        room_type = ROOM_TYPES.get(input("Выбор: ").strip())
        if not room_type:
            print("Ошибка выбора типа номера")
            return
        print("Статус: 1.Новая 2.Оплачено 3.Отменено 4.Прошедшее")
        status = STATUSES.get(input("Выбор: ").strip(), "Новая")
        payload = {
            "check_in": check_in,
            "check_out": check_out,
            "adults": adults,
            "children": children,
            "room_type": room_type,
            "status": status,
            "payment_method": None,
        }
        response, data = self._request("PUT", f"/api/admin/bookings/{booking_id}", json=payload)
        if response and response.status_code == 200:
            print("Бронирование изменено")
            return
        print(f"Ошибка: {data.get('error') if data else 'unknown'}")

    def delete_booking(self):
        if not self.is_admin:
            print("Удалять бронирования может только администратор")
            return
        try:
            booking_id = int(input("ID брони: ").strip())
        except ValueError:
            print("Ошибка ввода ID")
            return
        response, data = self._request("DELETE", f"/api/admin/bookings/{booking_id}")
        if response and response.status_code == 200:
            print("Бронирование удалено")
            return
        print(f"Ошибка: {data.get('error') if data else 'unknown'}")

    def admin_change_status(self):
        if not self.is_admin:
            print("Доступ только для администратора")
            return
        try:
            booking_id = int(input("ID брони: ").strip())
        except ValueError:
            print("Ошибка ввода ID")
            return
        print("1. Новая")
        print("2. Оплачено")
        print("3. Отменено")
        print("4. Прошедшее")
        status = STATUSES.get(input("Новый статус: ").strip())
        if not status:
            print("Ошибка выбора статуса")
            return
        response, data = self._request("PATCH", f"/api/admin/bookings/{booking_id}/status", json={"status": status})
        if response and response.status_code == 200:
            print("Статус изменён")
            return
        print(f"Ошибка: {data.get('error') if data else 'unknown'}")

    def filter_bookings(self):
        if not self.is_admin:
            print("Фильтр доступен только администратору")
            return
        print("\n1. Новые")
        print("2. Оплаченные")
        print("3. Отменённые")
        print("4. Прошедшие")
        status = STATUSES.get(input("Выбор: ").strip())
        if not status:
            print("Ошибка выбора статуса")
            return
        response, data = self._request("GET", "/api/admin/bookings", params={"status": status})
        if not response or response.status_code != 200:
            print("Не удалось получить бронирования")
            return
        items = data.get("items", [])
        if not items:
            print("Подходящих бронирований нет")
            return
        for item in items:
            print(
                f"[{item['id']}] {item['room_type']} | {item['check_in']} - {item['check_out']} | "
                f"{item['status']} | {item['price']} руб."
            )

    def save(self):
        if not self.is_admin:
            print("Сохранять может только администратор")
            return
        response, data = self._request("POST", "/api/admin/export", json={})
        if response and response.status_code == 200 and data.get("ok"):
            print("Данные сохранены")
            print(data.get("message", ""))
            return
        print(f"Ошибка сохранения: {data.get('message') if data else 'unknown'}")

    def load(self):
        if not self.is_admin:
            print("Загружать может только администратор")
            return
        response, data = self._request("POST", "/api/admin/import", json={})
        if response and response.status_code == 200 and data.get("ok"):
            print("Данные загружены")
            print(data.get("message", ""))
            return
        print(f"Ошибка загрузки: {data.get('message') if data else 'unknown'}")


def main():
    system = ConsoleSystem(BASE_URL)
    actions = {
        "1": system.register,
        "2": system.login_user,
        "3": system.login_admin,
        "4": system.add_booking,
        "5": system.show_my,
        "6": system.pay_booking,
        "7": system.admin_show_all_bookings,
        "8": system.admin_show_all_users,
        "9": system.edit_booking,
        "10": system.delete_booking,
        "11": system.admin_change_status,
        "12": system.filter_bookings,
        "13": system.save,
        "14": system.load,
        "15": system.logout,
        "0": lambda: sys.exit(0),
    }
    while True:
        print(
            """
================ МЕНЮ =================
1. Регистрация пользователя
2. Вход пользователя
3. Вход администратора
4. Добавить бронирование
5. Мои бронирования
6. Оплатить бронирование
--------- Панель администратора ---------
7. Показать все бронирования
8. Показать всех пользователей
9. Изменить бронирование
10. Удалить бронирование
11. Изменить статус бронирования
12. Фильтр бронирований
13. Сохранить
14. Загрузить
15. Выйти из аккаунта
0. Выход
=======================================
"""
        )
        choice = input(">> ").strip()
        action = actions.get(choice)
        if action:
            action()
        else:
            print("Ошибка выбора пункта меню")


if __name__ == "__main__":
    main()
