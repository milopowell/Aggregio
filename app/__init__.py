from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from config import Config

db = SQLAlchemy()
migrate = Migrate()

def create_app(config_class=Config):
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions with the application instance
    db.init_app(app)
    migrate.init_app(app, db)


    from . import helpers
    from .main.routes import main_bp
    from .aggregates.routes import aggregates_bp
    from .activities.routes import activities_bp

    @app.context_processor
    def inject_utility_functions():
        return dict(
            get_pace=helpers.get_pace,
            get_pace_per_100y=helpers.get_pace_per_100y,
            mps_to_mph=helpers.mps_to_mph,
            seconds_to_hms=helpers.seconds_to_hms,
            meters_to_miles=helpers.meters_to_miles,
            meters_to_feet=helpers.meters_to_feet
        )

    # Register blueprints with the app
    app.register_blueprint(main_bp)
    app.register_blueprint(aggregates_bp, url_prefix='/aggregates')
    app.register_blueprint(activities_bp, url_prefix='/activities')

    # Error handlers
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template('500.html'), 500

    return app