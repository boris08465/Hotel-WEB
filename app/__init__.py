from flask import Flask

from config import Config
from .db import close_db, init_db
from .routes import bp


def create_app(config_object=Config):
    app = Flask(
        __name__,
        instance_relative_config=False,
        template_folder="templates",
        static_folder="static",
    )
    app.config.from_object(config_object)

    app.config["DATABASE_PATH"].parent.mkdir(parents=True, exist_ok=True)

    app.teardown_appcontext(close_db)
    app.register_blueprint(bp)

    with app.app_context():
        init_db()

    return app
