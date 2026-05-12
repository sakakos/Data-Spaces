from api import app
import logging, os
import yaml, sys

# Port
port = int(os.environ.get("SATELLITE_PORT", 8080))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=port)
else:
    # Running inside gunicorn, set logger
    gunicorn_logger = logging.getLogger('gunicorn.error')
    app.logger.handlers = gunicorn_logger.handlers
    app.logger.setLevel(gunicorn_logger.level)
    app.logger.info("Setting gunicorn logger...")

# Load config
app.logger.info("Loading config from " + "config/satellite.yml")
try:
    with open("config/satellite.yml", "r") as stream:
        conf = yaml.safe_load(stream)
        app.logger.debug("... config loaded")
        app.config['satellite'] = conf['satellite']
except yaml.YAMLError as exc:
    app.logger.error('Error loading YAML: {}'.format(exc))
    sys.exit(4)
except FileNotFoundError as fnfe:
    app.logger.error('Could not load config file: {}'.format(fnfe))
    sys.exit(4)


