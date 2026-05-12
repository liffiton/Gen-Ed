# Container Deployment

This project can be deployed in a container using Podman or Docker. The instructions below focus on running the **CodeHelp** application, but any Gen-Ed application (such as Starburst) can be run by setting `FLASK_APP` accordingly.

The instructions below are for rootless Podman and use `podman` in examples, but `docker` can be used as a drop-in replacement for almost all commands.

## Build the Image

From the project root:

```bash
podman build -t gen-ed .
```

## Prerequisites

Before running the container, prepare the following:

1. **`.env` file** — Create a `.env` file with the required environment variables. See `README.md` for the full list. The container entrypoint specifically requires `FLASK_APP` and `FLASK_INSTANCE_PATH`, and the application requires others.

2. **Instance directory** — Create a directory to hold the database and other persistent files. You'll mount this inside the container at a path of your choice, then set `FLASK_INSTANCE_PATH` in `.env` to that same path. We recommend `/var/instance` as the mount-point path in the container.

   Optionally, create a `.well-known` folder inside your instance directory and place any `/.well-known` files here (e.g. for domain verification).

## Test via CLI

Run the container to verify it starts correctly:

```bash
podman run --rm \
    --env-file .env \
    -v ./instance:/var/instance:Z \
    -p 127.0.0.1:8080:8080 \
    gen-ed
```

> The `:Z` flag handles SELinux relabeling on Fedora/RHEL; on other systems, it is unneeded but harmless.

On first run, the container will initialize the database. On every run, it applies any pending migrations before starting the server. You should be able to reach the application at http://127.0.0.1:8080/ in your browser.

## Administration

Create an admin user by passing a Flask command through the entrypoint:

```bash
podman run --rm \
    --env-file .env \
    -v ./instance:/var/instance:Z \
    gen-ed flask newuser --admin username
```

The entrypoint handles environment validation and database initialization, then executes the `flask` command. A generated password will be printed to the terminal.

Other flask commands can be executed in a similar way.  See `README.md` and the output of `flask --help` for more.

## Run in Production with a Systemd Quadlet

Quadlets are the recommended way to manage Podman containers with systemd. These instructions create a rootless user-level service.

> You'll also want a reverse proxy (Caddy, Traefik, etc.) handling HTTPS and forwarding to `127.0.0.1:8080`. If you do, set `FLASK_APP_BEHIND_PROXY=1` in `.env` so forwarded headers are respected.

### Create the Unit File

We will create a systemd container service to launch and manage the
application.  For a few simple (optional) layers of security, we'll set it to
mount container filesystems read-only, and we'll run the application inside the
container with an unprivileged user.

Create `~/.config/containers/systemd/codehelp.container`:

```ini
[Unit]
Description=CodeHelp Container
After=network-online.target

[Container]
Image=localhost/gen-ed
EnvironmentFile=/absolute/path/to/.env
Volume=/absolute/path/to/instance:/var/instance:Z
PublishPort=127.0.0.1:8080:8080
# security: mount container filesystems read-only
ReadOnly=True
# security: run as unprivileged user (nobody) inside container
User=65534
# map uids so 'nobody' user can read/write mounted instance data
UserNS=keep-id:uid=65534,gid=65534

[Service]
Restart=on-failure

[Install]
WantedBy=default.target
```

Update the `EnvironmentFile` and `Volume` paths to match your actual `.env` and instance directory locations. The container-side path in `Volume` must match the `FLASK_INSTANCE_PATH` value in your `.env` file.

### Enable User Linger

This allows the user-level service to run on boot rather than only on user login:

```bash
sudo loginctl enable-linger $USER
```

### Manage the Service

```bash
# Reload systemd to recognize the new quadlet
systemctl --user daemon-reload

# Start the service
systemctl --user start gen-ed

# Check status
systemctl --user status gen-ed

# Enable on boot
systemctl --user enable gen-ed
```

### Updating

To deploy a new version, rebuild the image and restart the service:

```bash
podman build -t gen-ed .
systemctl --user restart gen-ed
```
