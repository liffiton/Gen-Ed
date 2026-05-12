#!/bin/sh
# Entrypoint script for use in containers

set -e   # fail/exit on any command error

# These can be set as env vars on the container; otherwise, we'll use these defaults.
THREADS="${THREADS:-10}"
CONNECTION_LIMIT="${CONNECTION_LIMIT:-100}"

if [ -z "$FLASK_APP" ]; then
    echo "FLASK_APP must be set (usually in .env)" >&2
    exit 1
fi

if [ -z "$FLASK_INSTANCE_PATH" ]; then
    echo "FLASK_INSTANCE_PATH must be set (usually in .env)" >&2
    exit 1
fi

# Initialize db on first run
if [ ! -f "${FLASK_INSTANCE_PATH}/.initialized" ]; then
    echo "First run: initializing database..."
    flask initdb
    touch "${FLASK_INSTANCE_PATH}/.initialized"
fi

case "$1" in
    serve)
        # apply migrations
        echo "Applying migrations..."
        flask migrate --auto
        # launch server
        echo "Starting server..."
        # trusting any IP as a proxy ("*") is acceptable *if* running in a container and publishing the port to localhost only
        exec waitress-serve --listen 0.0.0.0:8080 --trusted-proxy "*" --trusted-proxy-headers "x-forwarded-proto x-forwarded-host" --threads $THREADS --connection-limit $CONNECTION_LIMIT --call "${FLASK_APP}:create_app"
        ;;
    *)
        # pass through anything else; useful for manual "flask cmd" and other commands
        exec "$@"
        ;;
esac
