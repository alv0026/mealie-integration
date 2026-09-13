# Mealie integration

An authenticated FastAPI bridge for saving recipes from chat to an existing Mealie installation, searching recipes, retrieving a recipe, and updating selected fields. Developed against the live Mealie v3.25.1 OpenAPI schema.

The bridge and image publishing workflow are implemented. TrueNAS deployment, Cloudflare routing to the bridge, and the chat connection still need to be configured. Running this API alone does not connect it to a chat application.

## Local setup

Use Python 3.13 or newer. From this directory:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
```

Create `.env` from `.env.example` only if `.env` does not already exist. Set these values privately:

```dotenv
MEALIE_URL=https://m.tamaleopossuminspace.com
MEALIE_TOKEN=your_mealie_token
BRIDGE_API_KEY=a_separate_random_secret_of_at_least_32_characters
```

The Ubuntu development copy already has these configured. `.env` is ignored by Git and must remain private. Keep its permissions at `0600`. Use the bridge key to authenticate chat requests; only the bridge needs the Mealie token.

Start locally:

```bash
.venv/bin/uvicorn bridge.app:create_app --factory --env-file .env --host 127.0.0.1 --port 8000 --no-access-log
```

Open `http://127.0.0.1:8000/docs` for the API explorer. Click **Authorize** and enter the bridge key to test protected routes. The OpenAPI document is at `/openapi.json`.

## API

All recipe routes require `Authorization: Bearer <BRIDGE_API_KEY>`. Health and API documentation are public and contain no credentials.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | Process liveness; does not check upstream Mealie |
| GET | `/recipes/search?q=toast&page=1&per_page=20` | Search with pagination; maximum 50 results per page |
| GET | `/recipes/{slug}` | Retrieve a recipe by slug or ID |
| POST | `/recipes` | Create a recipe; requires an `Idempotency-Key` header |
| PATCH | `/recipes/{slug}` | Update only supplied fields |

Example creation body:

```json
{
  "name": "Toast",
  "description": "Simple breakfast toast",
  "ingredients": ["1 slice bread", "1 teaspoon butter"],
  "instructions": ["Toast the bread.", "Spread with butter."],
  "servings": 1,
  "prep_time": "2 minutes",
  "cook_time": "3 minutes"
}
```

Creation requires a name, at least one ingredient, and at least one instruction. Ingredients are stored as text notes, preserving the supplied quantities and wording without attempting to parse units or create food records. Updates accept the same fields, all optional. Omitted fields remain unchanged. Ingredient and instruction arrays replace the entire corresponding list; an empty list clears it. Nulls and unknown fields are rejected. No delete, account administration, or arbitrary upstream proxy routes are exposed.

### Repeated requests and interrupted saves

Send a new UUID in `Idempotency-Key` for each intended creation. Reuse that key with identical data when retrying. Successful retries return the stored creation result without creating another recipe. Reusing a key with different data returns 409.

Mealie creates a name first and saves recipe details in a second request. The bridge records its reservation in SQLite before creating anything. If either step times out or fails, it does not automatically repeat the creation. The error includes the slug when known. Retrieve that recipe and PATCH missing fields; if no slug is known, search Mealie before deciding whether to start another creation with a new key. A completed response is a receipt for the original creation, not a fresh copy of the recipe.

This protection depends on retaining the database. Keep the same `/data` volume across container updates and restarts. Deleting it removes the retry history. Distinct keys represent distinct creation attempts; the bridge does not merge recipes based on names. Use a single bridge instance with its own persistent SQLite volume.

## Verification

```bash
.venv/bin/python -m pytest -q
.venv/bin/python scripts/check_connection.py
```

Tests use a simulated Mealie server and never touch real recipes. They cover authentication, validation, request mapping, partial updates, sanitized upstream errors, concurrent creation reservations, and retries across restarts. The connection script uses the local `.env` and makes only read requests against the real server. It prints statuses, not recipes or secrets. Live creation and update behavior has not yet been tested against production recipes.

## Docker on the development VM

```bash
sudo docker compose -f compose.bridge.yaml up -d --build
sudo docker compose -f compose.bridge.yaml ps
curl http://127.0.0.1:8000/health
```

This starts only the bridge, bound to the VM's loopback address, with a persistent `bridge-data` volume. The image runs as UID/GID 10001. Its build context contains only the Python application and requirements; `.env` is excluded. Do not run `docker compose config` without `--quiet` when sharing output, because Compose can display resolved secrets.

The original `compose.yaml` is a separate, optional Mealie deployment scaffold. It is not needed when connecting to the existing TrueNAS Mealie instance.

## GitHub Container Registry

`.github/workflows/container.yml` runs the tests on pull requests and main-branch pushes. It builds the container after tests pass and publishes main-branch builds as:

- `ghcr.io/alv0026/mealie-integration:latest`
- `ghcr.io/alv0026/mealie-integration:sha-<full-commit-sha>`

The workflow uses GitHub's built-in `GITHUB_TOKEN` with package write permission. Do not add the Mealie token or bridge key to the workflow or build arguments. After the first publication, configure package visibility or TrueNAS registry credentials so TrueNAS can pull it. Prefer the commit tag for a fixed deployment version.

See [GitHub's container publishing documentation](https://docs.github.com/en/actions/tutorials/publish-packages/publish-docker-images) and [container registry access documentation](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry).

## TrueNAS deployment and chat connection

`deploy/truenas.compose.yaml` is a deployment template for a TrueNAS version that supports Custom App Compose YAML. Confirm the TrueNAS version and that port 30068 is available before installing it. Replace the credential placeholders privately in the TrueNAS UI; do not commit a filled-in copy. The template's Docker volume persists the retry database. If replacing it with a dataset mount, grant UID/GID 10001 write access.

The proposed bridge address on the LAN is `http://192.168.1.79:30068`. It is separate from Mealie's existing port 30067. After deployment, check `/health` and an authenticated search, then configure a dedicated HTTPS hostname in Cloudflare Tunnel that routes to the bridge. The existing `m.tamaleopossuminspace.com` remains the upstream Mealie address. Remote clients must use HTTPS because requests carry the bridge key.

The final chat integration method and bridge hostname still need to be selected. Keep these as separate steps: publish the image, deploy and verify the bridge, expose its HTTPS endpoint, and configure/test the chosen chat client.

## Mealie API references

Requests were checked against the installation's `/openapi.json` and the [v3.25.1 recipe controller](https://github.com/mealie-recipes/mealie/blob/v3.25.1/mealie/routes/recipe/recipe_crud_routes.py). General documentation: [Mealie API usage](https://docs.mealie.io/documentation/getting-started/api-usage/).
