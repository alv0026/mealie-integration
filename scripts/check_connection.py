"""Read-only check of the bridge and its live Mealie connection; prints no recipes or secrets."""
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from dotenv import dotenv_values
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge.app import create_app  # noqa: E402


def main():
    config = dotenv_values(Path(__file__).resolve().parents[1] / ".env")
    with TemporaryDirectory() as tmp:
        app = create_app(mealie_url=config.get("MEALIE_URL"), mealie_token=config.get("MEALIE_TOKEN"),
                         api_key=config.get("BRIDGE_API_KEY"), database=str(Path(tmp) / "check.sqlite3"))
        with TestClient(app) as client:
            headers = {"Authorization": "Bearer " + config["BRIDGE_API_KEY"]}
            response = client.get("/recipes/search", params={"q": "a", "per_page": 1}, headers=headers)
            print("Authenticated recipe search: HTTP", response.status_code)
            if response.status_code != 200:
                return 1
            data = response.json()
            if not isinstance(data, dict) or not isinstance(data.get("items"), list):
                print("Unexpected recipe search response structure.")
                return 1
            if data["items"]:
                slug = data["items"][0]["slug"]
                response = client.get("/recipes/" + slug, headers=headers)
                print("Authenticated recipe retrieval: HTTP", response.status_code)
                if response.status_code != 200:
                    return 1
            else:
                print("No matching recipe available for retrieval check.")
    print("Read-only connection check passed; no recipes changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
