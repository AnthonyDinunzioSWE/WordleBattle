from flask import Flask
from flask_dance.contrib.google import make_google_blueprint
from dotenv import load_dotenv
import os
from .Instances.instances import db, migrate, socketio, login_manager
from .Routes.routes import main
from .Routes.test_routes import test_bp

load_dotenv()

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = os.getenv('SQLALCHEMY_TRACK_MODIFICATIONS', False)

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    socketio.init_app(app)
    migrate.init_app(app, db)

    # Google OAuth setup
    google_bp = make_google_blueprint(
        client_id=os.getenv('GOOGLE_CLIENT_ID'),
        client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
        scope=[
            "https://www.googleapis.com/auth/userinfo.profile",
            "https://www.googleapis.com/auth/userinfo.email",
            "openid"
        ],
        redirect_to="main.google_authorized"  # Ensure this points to the correct route
    )
    app.register_blueprint(google_bp, url_prefix="/login")

    # Register routes
    app.register_blueprint(main)
    app.register_blueprint(test_bp)

    return app