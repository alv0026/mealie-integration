import hashlib
import hmac
import json
import os
import re
import sqlite3
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from typing import Annotated
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Path as ApiPath, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Line = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Slug = Annotated[str, ApiPath(min_length=1, max_length=250, pattern=r"^[\w-]+$")]


class RecipePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Name | None = None
    description: Annotated[str, Field(max_length=10000)] | None = None
    ingredients: Annotated[list[Line], Field(max_length=200)] | None = None
    instructions: Annotated[list[Line], Field(max_length=200)] | None = None
    servings: Annotated[float, Field(ge=0, le=100000, allow_inf_nan=False)] | None = None
    prep_time: Annotated[str, Field(max_length=100)] | None = None
    cook_time: Annotated[str, Field(max_length=100)] | None = None

    @model_validator(mode="after")
    def validate_changes(self):
        if not self.model_fields_set:
            raise ValueError("Supply at least one field to update.")
        if any(getattr(self, key) is None for key in self.model_fields_set):
            raise ValueError("Omit unchanged fields; null is not supported.")
        return self

    def mealie_payload(self):
        data = self.model_dump(exclude_unset=True)
        result = {}
        mapping = {"servings": "recipeServings", "prep_time": "prepTime", "cook_time": "cookTime"}
        for key, value in data.items():
            if key == "ingredients":
                result["recipeIngredient"] = [
                    {"note": line, "originalText": line, "quantity": 0, "referenceId": str(uuid4())}
                    for line in value
                ]
            elif key == "instructions":
                result["recipeInstructions"] = [{"text": line} for line in value]
            else:
                result[mapping.get(key, key)] = value
        return result


class RecipeCreate(RecipePatch):
    name: Name
    ingredients: Annotated[list[Line], Field(min_length=1, max_length=200)]
    instructions: Annotated[list[Line], Field(min_length=1, max_length=200)]


class CreationStore:
    """Reserve before writing upstream; never replay an uncertain creation."""

    def __init__(self, path):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS creations (key TEXT PRIMARY KEY, digest TEXT NOT NULL, slug TEXT, result TEXT)")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            with db:
                yield db
        finally:
            db.close()

    def reserve(self, key, digest):
        with self.connect() as db:
            cursor = db.execute("INSERT OR IGNORE INTO creations(key, digest) VALUES (?, ?)", (key, digest))
            if cursor.rowcount:
                return None
            old_digest, slug, result = db.execute("SELECT digest, slug, result FROM creations WHERE key = ?", (key,)).fetchone()
        if old_digest != digest:
            raise HTTPException(409, "Idempotency key was already used with different recipe data.")
        if result:
            return json.loads(result)
        raise HTTPException(409, {"message": "Creation is pending or its outcome is uncertain. Check Mealie before retrying with a new key; use PATCH to finish an existing recipe.", "slug": slug})

    def save_slug(self, key, slug):
        with self.connect() as db:
            db.execute("UPDATE creations SET slug = ? WHERE key = ?", (slug, key))

    def complete(self, key, result):
        with self.connect() as db:
            db.execute("UPDATE creations SET result = ? WHERE key = ?", (json.dumps(result), key))


def create_app(*, mealie_url=None, mealie_token=None, api_key=None, database=None, transport=None):
    base = (mealie_url or os.environ.get("MEALIE_URL", "")).rstrip("/")
    token = mealie_token or os.environ.get("MEALIE_TOKEN", "")
    key = api_key or os.environ.get("BRIDGE_API_KEY", "")
    parsed = urlsplit(base)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise RuntimeError("MEALIE_URL must be an HTTP(S) URL without embedded credentials, query, or fragment.")
    if not token or len(key) < 32:
        raise RuntimeError("Set MEALIE_TOKEN and a BRIDGE_API_KEY of at least 32 characters.")
    store = CreationStore(database or os.environ.get("BRIDGE_DB", "data/bridge.sqlite3"))

    @asynccontextmanager
    async def lifespan(app):
        async with httpx.AsyncClient(
            base_url=base + "/", headers={"Authorization": "Bearer " + token, "Accept": "application/json"},
            timeout=20, follow_redirects=False, transport=transport, trust_env=False,
        ) as client:
            app.state.mealie = client
            yield

    app = FastAPI(title="Mealie Recipe Bridge", version="0.1.0", lifespan=lifespan)
    bearer = HTTPBearer(auto_error=False)

    async def authenticate(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]):
        if credentials is None or not hmac.compare_digest(credentials.credentials.encode(), key.encode()):
            raise HTTPException(401, "Invalid bridge API key.", headers={"WWW-Authenticate": "Bearer"})

    async def upstream(method, path, **kwargs):
        try:
            response = await app.state.mealie.request(method, "api/" + path, **kwargs)
        except httpx.TimeoutException:
            raise HTTPException(504, "Mealie timed out. A write may have completed; check before retrying.") from None
        except httpx.RequestError:
            raise HTTPException(502, "Unable to reach Mealie.") from None
        if response.status_code in {404, 409, 422}:
            raise HTTPException(response.status_code, "Mealie rejected the recipe request.")
        if response.status_code == 429:
            raise HTTPException(503, "Mealie is rate limiting requests. Try again later.")
        if not response.is_success:
            raise HTTPException(502, "Mealie returned an error. Check upstream connectivity and credentials.")
        try:
            return response.json()
        except ValueError:
            raise HTTPException(502, "Mealie returned an unexpected response.") from None

    auth = [Depends(authenticate)]

    @app.get("/health", operation_id="health")
    async def health():
        return {"status": "ok"}

    @app.get("/recipes/search", dependencies=auth, operation_id="searchRecipes")
    async def search(q: Annotated[str, Query(min_length=1, max_length=200)], page: Annotated[int, Query(ge=1)] = 1, per_page: Annotated[int, Query(ge=1, le=50)] = 20):
        return await upstream("GET", "recipes", params={"search": q, "page": page, "perPage": per_page})

    @app.get("/recipes/{slug}", dependencies=auth, operation_id="getRecipe")
    async def get_recipe(slug: Slug):
        return await upstream("GET", "recipes/" + slug)

    @app.patch("/recipes/{slug}", dependencies=auth, operation_id="updateRecipe")
    async def update_recipe(slug: Slug, recipe: RecipePatch):
        """Only supplied fields change. Ingredient and instruction lists replace the entire list."""
        return await upstream("PATCH", "recipes/" + slug, json=recipe.mealie_payload())

    @app.post("/recipes", status_code=201, dependencies=auth, operation_id="createRecipe")
    async def create_recipe(recipe: RecipeCreate, idempotency_key: Annotated[str, Header(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")]):
        """Use a new UUID key per intended recipe; reuse the same key and data for retries."""
        digest = hashlib.sha256(recipe.model_dump_json().encode()).hexdigest()
        previous = store.reserve(idempotency_key, digest)
        if previous is not None:
            return previous
        slug = None
        try:
            slug = await upstream("POST", "recipes", json={"name": recipe.name})
            if not isinstance(slug, str) or not re.fullmatch(r"[\w-]{1,250}", slug):
                slug = None
                raise HTTPException(502, "Mealie did not return a valid recipe slug.")
            store.save_slug(idempotency_key, slug)
            await upstream("PATCH", "recipes/" + slug, json=recipe.mealie_payload())
            result = {"slug": slug, "status": "created"}
            store.complete(idempotency_key, result)
            return result
        except HTTPException as exc:
            raise HTTPException(exc.status_code, {
                "message": exc.detail, "slug": slug,
                "recovery": "Check Mealie before starting another creation. If a slug is present, GET it and PATCH any missing fields.",
            }) from None

    return app
