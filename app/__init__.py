from flask import Flask
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect

from config import Config
from .db import close_db, init_db
from .models import get_login_user
from .routes import bp

csrf = CSRFProtect()
login_manager = LoginManager()


def create_app(config_object=Config):
    app = Flask(
        __name__,
        instance_relative_config=False,
        template_folder="templates",
        static_folder="static",
    )
    app.config.from_object(config_object)

    app.config["DATABASE_PATH"].parent.mkdir(parents=True, exist_ok=True)

    csrf.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "main.login"
    login_manager.login_message = "Войдите в систему, чтобы продолжить."
    login_manager.login_message_category = "error"

    app.teardown_appcontext(close_db)
    app.register_blueprint(bp)

    with app.app_context():
        init_db()

    return app


@login_manager.user_loader
def load_user(user_id):
    return get_login_user(int(user_id))
