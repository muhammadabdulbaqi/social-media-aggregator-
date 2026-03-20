"""
Entry point for the Link Aggregator application.
Run with: python main.py   or   flask --app main run
"""
import os

from app import create_app

app = create_app(config_name=os.environ.get("FLASK_ENV", "development"))

if __name__ == "__main__":
    app.run(debug=app.config.get("DEBUG", True), port=5000)
