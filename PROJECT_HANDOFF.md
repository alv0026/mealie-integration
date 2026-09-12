# Mealie project handoff

## Purpose
Build a small API bridge so Aaron and Evelyn can save recipes from chat to Mealie, search existing recipes, retrieve a recipe, and update it.

## Current state
The Windows project contains only a Mealie deployment scaffold: compose.yaml, .env, .env.example, .gitignore, README.md and .git metadata. The bridge application has NOT been implemented. Docker and Podman were unavailable on the Windows PC when scaffolding was done. No running Mealie database or Docker volume was migrated in this package.

The scaffold uses SQLite, a persistent mealie-data Docker volume, and host port 9925. The earlier task selected Mealie v3.25.1; inspect .env for actual values. Verify compatibility before changing versions. The existing README commands also work in a Linux shell.

## Intended architecture (planned, not deployed)
Chat integration -> Cloudflare Tunnel -> authenticated Python/FastAPI bridge -> Mealie API.
The chat integration mechanism still needs to be selected and tested; merely exposing REST endpoints does not create a working ChatGPT integration.
Build the bridge image via GitHub Actions, publish to GitHub Container Registry, and deploy as a TrueNAS Custom App. Ubuntu is the development machine; final hosting on TrueNAS was the earlier plan and can be revisited.
Suggested components: Python, FastAPI, uvicorn, httpx, Dockerfile. Python 3.13-slim was discussed as a candidate base image, not a finalized dependency pin.
Suggested bridge routes: GET /health, POST /recipes, GET /recipes/search?q=..., GET /recipes/{slug}, PATCH /recipes/{slug}. These are proposed bridge routes, not verified Mealie API endpoints.
Suggested runtime variables: MEALIE_URL, MEALIE_TOKEN, BRIDGE_API_KEY. Keep tokens out of source control and images. Authenticate chat access separately from the token used by the bridge to access Mealie. Expose only the intended recipe operations.
The previously discussed Mealie URL was https://m.tamaleopossuminspace.com; verify its current role and availability before use.

## Ubuntu destination
Host: 192.168.1.52
Account: aron2002
Suggested project directory: ~/projects/mealie-container
SSH: port 22
RDP: port 3389. xrdp is running. UFW originally allowed only SSH; the user added an RDP allow rule from Windows IP 192.168.1.119, resolving connectivity.

## Next work
1. Inspect the copied repository and Git status. Preserve .env and keep it private.
2. Check Ubuntu Docker/Podman availability and choose the development runtime.
3. Clarify whether to use an existing Mealie installation or launch this scaffold as a development instance. Existing recipes on TrueNAS require a separate backup/migration if moving that service is desired.
4. Inspect the actual Mealie version and API schema before implementing API requests.
5. Implement and test the authenticated bridge, including failed authentication, input validation, upstream failures and duplicate creation handling.
6. Configure the chosen chat integration, container build/publish workflow, and deployment after local validation.

## Source conversations
- Mealie Setup Guidance (ChatGPT), September 5, 2026: bridge architecture, recipe workflow for Evelyn, GHCR and TrueNAS deployment plan.
- Set up Mealie container project (Codex), September 6, 2026: copied repository outside OneDrive and created deployment scaffold. Work paused pending a development machine.
- Current RDP and migration task, September 12, 2026: confirmed Ubuntu destination and authorized transfer.

## Original locations
Working project: C:\Users\aaron\Documents\Codex\Projects\mealie-container
An earlier empty repository copy was left at C:\Users\aaron\OneDrive\Documents\ChatGPT\Mealie container. No files from that old location are needed for the scaffold described above.
The Windows working copy is retained as a backup; this package does not delete it.
