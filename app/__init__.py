import os
from flask import Flask
from dotenv import load_dotenv

load_dotenv()

def create_app():
    app = Flask(__name__)

    # --- Configuration ---
    app.config["MONGO_URI"] = os.getenv("MONGO_URI")
    app.config["GITHUB_WEBHOOK_SECRET"] = os.getenv("GITHUB_WEBHOOK_SECRET")

    if not app.config["MONGO_URI"]:
        app.logger.warning("MONGO_URI is not set. MongoDB functionality will be affected.")

    # --- Initialize Extensions ---
    from .extensions import mongo
    try:
        mongo.init_app(app)
        app.logger.info("MongoDB initialized successfully.")
    except Exception as e:
        app.logger.error(f"Failed to initialize MongoDB: {e}")


    # --- Register Blueprints ---
    from app.webhook.routes import webhook_bp
    app.register_blueprint(webhook_bp)
    app.logger.info("Webhook blueprint registered.")

    try:
        from app.ui.routes import ui_bp
        app.register_blueprint(ui_bp)
        app.logger.info("UI blueprint registered.")
    except ImportError:
        app.logger.info("UI blueprint not found or not registered. UI will not be available via this blueprint.")


    @app.route('/health')
    def health_check():
        return "Webhook receiver is healthy!"

    return app
