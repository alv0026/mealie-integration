# Mealie container

A small Docker Compose deployment of [Mealie](https://mealie.io/) using SQLite and a Docker-managed data volume.

## Requirements

- Docker Desktop or Docker Engine
- Docker Compose v2 (`docker compose`)

## Start

```powershell
docker compose up -d
docker compose ps
```

Open <http://localhost:9925>.

The initial Mealie credentials are:

- Username: `changeme@example.com`
- Password: `MyPassword`

Change the password immediately after signing in.

## Common commands

```powershell
# Follow logs
docker compose logs -f mealie

# Stop the service without deleting its data
docker compose down

# Pull the configured image and restart
docker compose pull
docker compose up -d
```

## Configuration

Local settings live in `.env`, which Git ignores. Keep `.env.example` updated with safe example values.

Before exposing Mealie beyond this computer, change `BASE_URL` to its final HTTPS address and place it behind a properly configured reverse proxy.

## Data and backups

Mealie stores application data in the Docker volume `mealie-data`. Do not run `docker compose down --volumes` unless you intend to delete that data.

Create Mealie backups from its administration interface and copy the resulting backup files to another device or storage service. A backup stored only on this computer is not sufficient protection.
