# Mealie project handoff

## Current checkpoint — September 13, 2026

The authenticated Python/FastAPI bridge is implemented locally, with tests, a Dockerfile, a development Compose file, a TrueNAS deployment template, and a GitHub Actions test/build/publish workflow. The original Mealie deployment scaffold is retained. The next checkpoint must record whether the new bridge commit was pushed and whether its GitHub Actions run passed.

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
- Docker 29.1.3 and Compose 2.40.3 are installed; the Docker service was verified active. This agent session cannot access the Docker socket as the user, and `sudo -n docker build` requires interactive authentication. Local container build has not been verified; use GitHub Actions or have the user run the documented sudo Compose command.
- GitHub CLI authentication works outside the sandbox with repo/workflow scopes. Network failures inside the sandbox can produce misleading authentication errors.
- TestClient stalls under the sandbox; the same tests pass quickly outside it. Use escalated test execution where required.
- Python virtual environment `.venv` contains runtime/test dependencies. FastAPI/Starlette currently emit deprecation warnings for their httpx-based TestClient, but tests pass.

## Deployment plan

GitHub Actions tests the bridge and builds/publishes `ghcr.io/alv0026/mealie-integration:latest` and `sha-<full-commit-sha>` on main. Runtime secrets are not needed in GitHub. The image uses Python 3.13 and UID/GID 10001, with persistent state at `/data/bridge.sqlite3`.

`compose.bridge.yaml` runs the bridge locally on loopback port 8000. `deploy/truenas.compose.yaml` proposes LAN port 30068 on TrueNAS and must have placeholders filled privately before use. Confirm TrueNAS version and port availability. Verify GHCR package access before pulling. Retain the state volume across updates.

After deployment, configure a separate Cloudflare HTTPS hostname for the bridge. Keep `m.tamaleopossuminspace.com` pointing to Mealie. The final chat integration mechanism and bridge hostname are not selected. An asynchronous question was sent asking whether users want a dedicated recipe GPT, regular ChatGPT conversations, or another chat app; check for a reply before choosing the connector method. Merely exposing this REST API does not create a working chat integration.

## Next work

1. Finish verification/review, commit and push bridge files, and monitor GitHub Actions. Record the actual run outcome.
2. Resolve any build or registry publication failures.
3. Confirm TrueNAS version and deploy the image with private runtime credentials and persistent state.
4. Verify the deployed bridge, configure its Cloudflare hostname, and configure the chosen chat integration.
5. Run an explicitly identified end-to-end recipe save/update test. Mocked writes are verified; production writes are not yet exercised.

## Migration history

Originally scaffolded on Windows at `C:\Users\aaron\Documents\Codex\Projects\mealie-container` and transferred to Ubuntu on September 12. Transfer archive: `~/mealie-project-transfer.tar.gz`. The Windows copy remains a backup. No Mealie database or Docker volume was migrated. Ubuntu is the development VM at 192.168.1.52; TrueNAS is the intended final host.
