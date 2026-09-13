# Mealie project handoff

## Current checkpoint — September 13, 2026

The authenticated Python/FastAPI bridge is implemented locally, with tests, a Dockerfile, a development Compose file, a TrueNAS deployment template, and a GitHub Actions test/build/publish workflow. The original Mealie deployment scaffold is retained. Implementation commit `15c6fdf5fb0fe851b603ea42d0ff5d75c34af09c` was pushed to `main`. GitHub Actions run https://github.com/alv0026/mealie-integration/actions/runs/34752868488 passed both the Python 3.13 tests and container build/publication. The image is published as `ghcr.io/alv0026/mealie-integration:latest` and `ghcr.io/alv0026/mealie-integration:sha-15c6fdf5fb0fe851b603ea42d0ff5d75c34af09c`. It has been deployed to TrueNAS.

## TrueNAS deployment preparation

User confirmed TrueNAS **24.10.2.2**. Official 24.10 documentation confirms Apps > Discover Apps > three-dot menu > Install via YAML. Anonymous GHCR manifest access returned HTTP 200, so no registry login is needed for the published image. Prepared `data/truenas.compose.yaml` with runtime credentials filled in, mode 0600, ignored by Git, and pinned to the verified implementation image tag. Never display its contents in chat or commit it. The user must paste it privately into TrueNAS and save the app as `mealie-bridge`. Proposed port is 30068; its availability has not been checked on TrueNAS. Deployment has been performed or verified.

## Project and target

- Local project: `/home/aron2002/projects/mealie-container`.
- Repository: `https://github.com/alv0026/mealie-integration.git`, branch `main`.
- Users: Aaron and Evelyn want to save recipes from chat, search, retrieve, and update recipes.
- Connect to the existing TrueNAS Mealie installation, confirmed by the user as **v3.25.1**. Do not launch another Mealie instance as part of bridge deployment.
- Working upstream URL: `https://m.tamaleopossuminspace.com`.
- User-supplied LAN URL: `http://192.168.1.79:30067/`. Earlier agent checks could not connect to it. Public HTTPS now works, so local connectivity is not a blocker for bridge development.

## Private configuration

The existing `.env` contains `MEALIE_URL`, the user-provided `MEALIE_TOKEN`, and a separately generated `BRIDGE_API_KEY`. Its permissions are 0600 and Git ignores it. Never print credentials or copy them into source, logs, chat, Docker images, or handoff notes. The bridge key is the client credential; the Mealie token is only for the bridge-to-Mealie connection.

## Implemented behavior

- Public `/health` liveness and `/docs` / `/openapi.json` documentation.
- Bearer-authenticated recipe search, retrieval, creation, and PATCH routes.
- Validated name, description, ingredient/instruction text lists, servings, and preparation/cooking times.
- Updates send only specified fields and do not expose settings/ownership changes.
- Creation uses Mealie's name-only POST followed by a details PATCH, verified against the live API schema and v3.25.1 controller source.
- Required creation idempotency keys backed by persistent SQLite reservations. Successful retries return the original receipt; failed or uncertain saves require inspection/recovery rather than repeating a POST. Known partial-save slugs are included in errors. Distinct keys are distinct creation attempts.
- No delete operation or arbitrary URL proxy.
- Upstream errors are sanitized; no automatic write retries or redirect following.

## Verification and environment

- 22 mocked tests passed on Python 3.14.4 outside the sandbox. They cover authentication, validation, payload mapping, partial updates, errors, concurrent reservations, and durable retries.
- A live read-only search through the bridge returned HTTP 200. Search term `a` returned no items, so live recipe retrieval was skipped. No production recipe was created or changed.
- Public `/api/app/about` and authenticated `/api/users/self` returned HTTP 200 JSON during the earlier connection check. The previous HTTP 403 no longer reproduces.
- Development Compose validates with `docker compose -f compose.bridge.yaml config --quiet`.
- Docker 29.1.3 and Compose 2.40.3 are installed; the Docker service was verified active. This agent session cannot access the Docker socket as the user, and `sudo -n docker build` requires interactive authentication. Local container build has not been verified, but the GitHub Actions container build and registry upload succeeded. The user can run the documented sudo Compose command for a local runtime check.
- GitHub CLI authentication works outside the sandbox with repo/workflow scopes. Network failures inside the sandbox can produce misleading authentication errors.
- TestClient stalls under the sandbox; the same tests pass quickly outside it. Use escalated test execution where required.
- Python virtual environment `.venv` contains runtime/test dependencies. FastAPI/Starlette currently emit deprecation warnings for their httpx-based TestClient, but tests pass.

## Deployment plan

GitHub Actions tests the bridge and builds/publishes `ghcr.io/alv0026/mealie-integration:latest` and `sha-<full-commit-sha>` on main. Runtime secrets are not needed in GitHub. The image uses Python 3.13 and UID/GID 10001, with persistent state at `/data/bridge.sqlite3`.

`compose.bridge.yaml` runs the bridge locally on loopback port 8000. `deploy/truenas.compose.yaml` proposes LAN port 30068 on TrueNAS and must have placeholders filled privately before use. Confirm TrueNAS version and port availability. Verify GHCR package access before pulling. Retain the state volume across updates.

After deployment, configure a separate Cloudflare HTTPS hostname for the bridge. Keep `m.tamaleopossuminspace.com` pointing to Mealie. The final chat integration mechanism and bridge hostname are not selected. An asynchronous question was sent asking whether users want a dedicated recipe GPT, regular ChatGPT conversations, or another chat app; check for a reply before choosing the connector method. Merely exposing this REST API does not create a working chat integration.

## Next work

1. Confirm TrueNAS version and GHCR package visibility/access, then deploy the published image with private runtime credentials and persistent state.
2. Verify the deployed bridge, configure its Cloudflare hostname, and configure the chosen chat integration.
3. Run an explicitly identified end-to-end recipe save/update test. Mocked writes are verified; production writes are not yet exercised.

## Migration history

Originally scaffolded on Windows at `C:\Users\aaron\Documents\Codex\Projects\mealie-container` and transferred to Ubuntu on September 12. Transfer archive: `~/mealie-project-transfer.tar.gz`. The Windows copy remains a backup. No Mealie database or Docker volume was migrated. Ubuntu is the development VM at 192.168.1.52; TrueNAS is the intended final host.

 ## Deployment and verification

  The bridge is deployed on TrueNAS 24.10.2.2 and available at
  https://mb.tamaleopossuminspace.com. The health and OpenAPI endpoints
  respond successfully. Authenticated recipe search and recipe creation
  through Mealie Assistant in ChatGPT have been tested successfully.
  Runtime credentials remain private and must not be committed.
