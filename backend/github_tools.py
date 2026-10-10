"""Tools that let agents write to the project's GitHub repo via the Contents API."""

import base64
import os
from urllib.parse import quote

import requests
from google.genai import types

GITHUB_API = "https://api.github.com"
TIMEOUT = 30

WRITE_CODE_FILE = types.FunctionDeclaration(
    name="write_code_file",
    description=(
        "Create or update a file in the project's GitHub repository and commit it. "
        "Overwrites the whole file, so always pass the complete file content."
    ),
    parameters_json_schema={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "File path relative to the repo root, e.g. 'frontend/src/Button.jsx'.",
            },
            "content": {"type": "string", "description": "The full content of the file."},
            "commit_message": {"type": "string", "description": "A clear, short commit message."},
        },
        "required": ["path", "content", "commit_message"],
    },
)


def write_code_file(path: str, content: str, commit_message: str) -> dict:
    """Create or update `path` in GITHUB_REPO. Returns {tool_used, url} or {error}."""
    repo = os.getenv("GITHUB_REPO")
    token = os.getenv("GITHUB_TOKEN")
    if not repo or not token:
        return {"error": "GITHUB_REPO and GITHUB_TOKEN must be set in backend/.env"}

    path = path.strip().lstrip("/")
    if not path:
        return {"error": "path must not be empty"}

    url = f"{GITHUB_API}/repos/{repo}/contents/{quote(path)}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    body = {
        "message": commit_message,
        "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
    }

    try:
        # Updating an existing file requires its current sha.
        existing = requests.get(url, headers=headers, timeout=TIMEOUT)
        if existing.status_code == 200:
            data = existing.json()
            if not isinstance(data, dict) or data.get("type") != "file":
                return {"error": f"{path} exists but is not a file"}
            body["sha"] = data["sha"]
        elif existing.status_code != 404:
            return {"error": _github_error(existing)}

        response = requests.put(url, headers=headers, json=body, timeout=TIMEOUT)
        if response.status_code not in (200, 201):
            return {"error": _github_error(response)}
    except requests.RequestException as e:
        return {"error": f"GitHub request failed: {e}"}

    return {
        "tool_used": f"wrote {path} to GitHub",
        "url": response.json()["content"]["html_url"],
    }


def _github_error(response: requests.Response) -> str:
    try:
        message = response.json().get("message", response.text)
    except ValueError:
        message = response.text
    return f"GitHub API error ({response.status_code}): {message}"
