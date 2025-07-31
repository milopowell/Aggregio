from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from config import Config

# Create extension instances without an app object
db = SQLAlchemy()
migrate = Migrate()

def create_app(config_class=Config):
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)

    @app.context_processor
    def inject_utility_functions():
        return dict(
            get_pace=helpers.get_pace,
            mps_to_mph=helpers.mps_to_mph,
            seconds_to_hms=helpers.seconds_to_hms,
            meters_to_miles=helpers.meters_to_miles,
            meters_to_feet=helpers.meters_to_feet
        )

    # Import and register blueprints
    from .main.routes import main_bp
    from .aggregates.routes import aggregates_bp
    from .activities.routes import activities_bp

    # Register blueprints or routes here
    app.register_blueprint(main_bp)
    app.register_blueprint(aggregates_bp, url_prefix='/aggregates')
    app.register_blueprint(activities_bp, url_prefix='/activities')

    return app