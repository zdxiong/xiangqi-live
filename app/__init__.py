from flask import Flask

from app.config import Config


def create_app(config_class=Config):
    """Flask 应用工厂。"""
    app = Flask(__name__)
    app.config.from_object(config_class)

    from app.api.routes import bp as api_bp
    app.register_blueprint(api_bp)

    return app
