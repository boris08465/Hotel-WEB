import os
import sys
from getpass import getpass

import requests


BASE_URL = os.environ.get("HOTEL_API_URL", "http://127.0.0.1:5000").rstrip("/")


class AdminConsole:
    def __init__(self, base_url):
        self.base_url = base_url
        self.session = requests.Session()

    def run(self):
        print(f"API: {self.base_url}")
        if not self.login():
            print("Не удалось войти.")
            return 1
        while True:
            print("\n--- Админ-меню ---")
            print("1) Список пользователей")
            print("2) Список бронирований")
            print("3) Изменить статус бронирования")
            print("4) Редактировать бронирование")
            print("5) Удалить бронирование")
            print("6) Импорт из data/import_data.pkl")
            print("0) Выход")
            choice = input("Выберите пункт: ").strip()
            if choice == "1":
                self.list_users()
            elif choice == "2":
                self.list_bookings()
            elif choice == "3":
                self.change_status()
            elif choice == "4":
                self.edit_booking()
            elif choice == "5":
                self.delete_booking()
            elif choice == "6":
                self.import_data()
            elif choice == "0":
                self.logout()
                print("Выход.")
                return 0
            else:
                print("Неизвестный пункт меню.")

    def _request(self, method, path, **kwargs):
        url = f"{self.base_url}{path}"
        try:
            response = self.session.request(method, url, timeout=10, **kwargs)
        except requests.RequestException as exc:
            print(f"Ошибка соединения: {exc}")
            return None, None
        try:
            payload = response.json()
        except ValueError:
            payload = None
        return response, payload

    def login(self):
        print("Авторизация администратора")
        login = input("Логин (email/телефон): ").strip()
        password = getpass("Пароль: ")
        response, payload = self._request(
            "POST",
            "/api/auth/login",
            json={"login": login, "password": password},
        )
        if not response:
            return False
        if response.status_code != 200:
            print("Ошибка авторизации.")
            return False
        if payload["user"]["role"] != "admin":
            print("Пользователь не администратор.")
            return False
        print(f"Вход выполнен: {payload['user']['name']}")
        return True

    def logout(self):
        self._request("POST", "/api/auth/logout", json={})

    def list_users(self):
        response, payload = self._request("GET", "/api/admin/users")
        if not response or response.status_code != 200:
            print("Не удалось получить пользователей.")
            return
        print("\nПользователи:")
        for idx, user in enumerate(payload["items"], start=1):
            print(f"{idx:>3}. id={user['id']} {user['surname']} {user['name']} | {user['email']} | {user['role']}")

    def _load_bookings(self, status=None):
        params = {"status": status} if status else None
        response, payload = self._request("GET", "/api/admin/bookings", params=params)
        if not response or response.status_code != 200:
            print("Не удалось получить бронирования.")
            return []
        return payload["items"]

    def list_bookings(self):
        status = input("Фильтр по статусу (пусто = все): ").strip() or None
        bookings = self._load_bookings(status=status)
        self._print_bookings(bookings)

    def _print_bookings(self, bookings):
        if not bookings:
            print("Бронирований нет.")
            return
        print("\nБронирования:")
        for idx, item in enumerate(bookings, start=1):
            print(
                f"{idx:>3}. id={item['id']} user={item['user_id']} room={item['room_type']} "
                f"{item['check_in']}..{item['check_out']} status={item['status']} price={item['price']}"
            )

    def _pick_booking_id(self, prompt):
        bookings = self._load_bookings()
        self._print_bookings(bookings)
        if not bookings:
            return None
        raw = input(f"{prompt} (номер из списка): ").strip()
        if not raw.isdigit():
            print("Нужно ввести номер строки.")
            return None
        pos = int(raw) - 1
        if pos < 0 or pos >= len(bookings):
            print("Нет такого номера в текущем списке.")
            return None
        # Важно: работаем по реальному id, а не по порядковому номеру строки.
        return bookings[pos]["id"]

    def change_status(self):
        booking_id = self._pick_booking_id("Выберите бронирование для смены статуса")
        if not booking_id:
            return
        status = input("Новый статус (Новая/Оплачено/Отменено/Прошедшее): ").strip()
        response, payload = self._request(
            "PATCH",
            f"/api/admin/bookings/{booking_id}/status",
            json={"status": status},
        )
        if response and response.status_code == 200:
            print("Статус обновлен.")
        else:
            print(f"Ошибка: {payload.get('error') if payload else 'unknown'}")

    def edit_booking(self):
        booking_id = self._pick_booking_id("Выберите бронирование для редактирования")
        if not booking_id:
            return
        print("Введите новые значения.")
        payload = {
            "check_in": input("Заезд (YYYY-MM-DD): ").strip(),
            "check_out": input("Выезд (YYYY-MM-DD): ").strip(),
            "adults": input("Взрослые: ").strip(),
            "children": input("Дети: ").strip(),
            "room_type": input("Тип номера (Стандарт/Комфорт/Люкс): ").strip(),
            "status": input("Статус (Новая/Оплачено/Отменено/Прошедшее): ").strip(),
            "payment_method": input("Способ оплаты (или пусто): ").strip() or None,
        }
        response, data = self._request("PUT", f"/api/admin/bookings/{booking_id}", json=payload)
        if response and response.status_code == 200:
            print("Бронирование обновлено.")
        else:
            print(f"Ошибка: {data.get('error') if data else 'unknown'}")

    def delete_booking(self):
        booking_id = self._pick_booking_id("Выберите бронирование для удаления")
        if not booking_id:
            return
        confirm = input(f"Удалить бронирование id={booking_id}? (yes/no): ").strip().lower()
        if confirm != "yes":
            print("Отменено.")
            return
        response, data = self._request("DELETE", f"/api/admin/bookings/{booking_id}")
        if response and response.status_code == 200:
            print("Бронирование удалено.")
        else:
            print(f"Ошибка: {data.get('error') if data else 'unknown'}")

    def import_data(self):
        response, data = self._request("POST", "/api/admin/import", json={})
        if response and response.status_code == 200 and data.get("ok"):
            print(data["message"])
            return
        print(f"Ошибка импорта: {data.get('message') if data else 'unknown'}")


def main():
    console = AdminConsole(BASE_URL)
    return console.run()


if __name__ == "__main__":
    sys.exit(main())
