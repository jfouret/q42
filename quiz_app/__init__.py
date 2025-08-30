from flask import Flask, request, redirect, url_for, g, session
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, verify_jwt_in_request, get_jwt_identity
import os
import markdown
from jinja2 import pass_context
from markupsafe import Markup

# Initialize extensions
db = SQLAlchemy()
jwt = JWTManager()

def create_app():
    """Create and configure an instance of the Flask application."""
    app = Flask(__name__, instance_relative_config=True)
    
    # Load configuration from config.py
    app.config.from_object('config.Config')

    # Configure JWT
    app.config["JWT_TOKEN_LOCATION"] = ["cookies"]
    app.config["JWT_COOKIE_CSRF_PROTECT"] = False # Keep it simple for this use case

    # Ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    # Initialize extensions with the app
    db.init_app(app)
    jwt.init_app(app)

    # Custom Markdown filter
    @app.template_filter('markdown')
    @pass_context
    def markdown_filter(context, value):
        return Markup(markdown.markdown(value, extensions=['fenced_code']))

    @app.before_request
    def before_request_hook():
        # The login page and static files should be accessible without a JWT
        if request.endpoint and (request.endpoint.startswith('auth.') or request.endpoint == 'static'):
            return

        try:
            verify_jwt_in_request()
            g.user = get_jwt_identity()
        except Exception as e:
            return redirect(url_for('auth.login'))

    with app.app_context():
        # Import parts of our application
        from . import routes
        from . import auth
        from .models import Question # Import models here
        
        # Create database tables for our models
        db.create_all()

        # Load questions into the database
        from .quiz_logic import load_questions_from_json
        questions_dir = app.config.get('QUESTIONS_DIR')
        if questions_dir:
            load_questions_from_json(questions_dir)

        # Register blueprints
        app.register_blueprint(routes.main_bp)
        app.register_blueprint(auth.auth_bp)

        return app
