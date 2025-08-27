from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import os
import markdown
from jinja2 import pass_context
from markupsafe import Markup

# Initialize extensions
db = SQLAlchemy()

def create_app():
    """Create and configure an instance of the Flask application."""
    app = Flask(__name__, instance_relative_config=True)
    
    # Load configuration from config.py
    app.config.from_object('config.Config')

    # Ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    # Initialize extensions with the app
    db.init_app(app)

    # Custom Markdown filter
    @app.template_filter('markdown')
    @pass_context
    def markdown_filter(context, value):
        return Markup(markdown.markdown(value, extensions=['fenced_code']))

    with app.app_context():
        # Import parts of our application
        from . import routes
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

        return app
