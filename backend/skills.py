"""Load Agent Skills (https://agentskills.io) from the skills/ folder.

A skill is a folder containing a SKILL.md file: YAML frontmatter with at least
`name` and `description`, followed by markdown instructions.

    skills/
      code-review/
        SKILL.md

Skills are scanned once when this module is imported; call load_skills() to rescan.
create_skill() writes a new skill folder and registers it immediately.
"""

import logging
import re
import shutil
from pathlib import Path

import yaml

SKILLS_DIR = Path(__file__).parent / "skills"

# Agent Skills spec: 1-64 chars, lowercase letters/numbers/hyphens, no leading, trailing or
# consecutive hyphens. The description must be 1-1024 chars.
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MAX_NAME_LENGTH = 64
MAX_DESCRIPTION_LENGTH = 1024

logger = logging.getLogger(__name__)

_FRONTMATTER_RE = re.compile(r"\A---[ \t]*\n(.*?)\n---[ \t]*(?:\n|\Z)(.*)\Z", re.DOTALL)

_skills: dict[str, dict] = {}


class InvalidSkillError(ValueError):
    """The requested skill name or content doesn't meet the Agent Skills spec."""


class SkillExistsError(Exception):
    """A skill (or skill folder) with that name already exists."""


def _parse_skill_md(path: Path) -> dict:
    """Parse a SKILL.md file into {name, description, instructions}. Raises ValueError if invalid."""
    text = path.read_text(encoding="utf-8-sig")
    match = _FRONTMATTER_RE.match(text)
    if not match:
        raise ValueError("missing YAML frontmatter (file must start with a '---' block)")

    try:
        frontmatter = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError as e:
        raise ValueError(f"invalid YAML frontmatter: {e}") from e
    if not isinstance(frontmatter, dict):
        raise ValueError("frontmatter must be a YAML mapping")

    name = frontmatter.get("name")
    description = frontmatter.get("description")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("frontmatter is missing a 'name'")
    if not isinstance(description, str) or not description.strip():
        raise ValueError("frontmatter is missing a 'description'")

    return {
        "name": name.strip(),
        "description": description.strip(),
        "instructions": match.group(2).strip(),
    }


def load_skills(skills_dir: Path = SKILLS_DIR) -> int:
    """Scan skills_dir and replace the loaded skills. Returns the number of skills loaded."""
    skills: dict[str, dict] = {}

    if not skills_dir.is_dir():
        logger.warning("Skills folder not found: %s", skills_dir)
    else:
        for folder in sorted(p for p in skills_dir.iterdir() if p.is_dir()):
            skill_md = folder / "SKILL.md"
            if not skill_md.is_file():
                continue
            try:
                skill = _parse_skill_md(skill_md)
            except (OSError, ValueError) as e:
                logger.warning("Skipping skill %s: %s", folder.name, e)
                continue

            if skill["name"] != folder.name:
                logger.warning(
                    "Skill name %r does not match its folder name %r", skill["name"], folder.name
                )
            if skill["name"] in skills:
                logger.warning("Skipping duplicate skill name %r in %s", skill["name"], folder.name)
                continue
            skills[skill["name"]] = skill

    _skills.clear()
    _skills.update(skills)
    logger.info("Loaded %d skill(s) from %s", len(_skills), skills_dir)
    return len(_skills)


def list_skills() -> list[dict]:
    """Return [{name, description}] for every loaded skill, sorted by name."""
    return [
        {"name": s["name"], "description": s["description"]}
        for s in sorted(_skills.values(), key=lambda s: s["name"])
    ]


def get_skill(name: str) -> dict | None:
    """Return {name, description, instructions} for a skill, or None if it doesn't exist."""
    skill = _skills.get(name)
    return dict(skill) if skill else None


def validate_name(name: str) -> None:
    """Raise InvalidSkillError unless `name` is a valid Agent Skills name."""
    if not 1 <= len(name) <= MAX_NAME_LENGTH:
        raise InvalidSkillError(f"Name must be 1-{MAX_NAME_LENGTH} characters long.")
    if not NAME_RE.match(name):
        raise InvalidSkillError(
            "Name may only contain lowercase letters, numbers and single hyphens, "
            "and can't start or end with a hyphen (e.g. 'sales-agent')."
        )


def create_skill(name: str, description: str, instructions: str, skills_dir: Path | None = None) -> dict:
    """Write skills/<name>/SKILL.md and register the skill. Returns {name, description}.

    Raises InvalidSkillError for a bad name or content, SkillExistsError if it already exists.
    """
    skills_dir = skills_dir or SKILLS_DIR
    description, instructions = description.strip(), instructions.strip()
    validate_name(name)
    if not 1 <= len(description) <= MAX_DESCRIPTION_LENGTH:
        raise InvalidSkillError(f"Description must be 1-{MAX_DESCRIPTION_LENGTH} characters long.")
    if not instructions:
        raise InvalidSkillError("Role prompt must not be empty.")
    if name in _skills:
        raise SkillExistsError(f"An agent named '{name}' already exists.")

    folder = skills_dir / name
    skills_dir.mkdir(parents=True, exist_ok=True)
    try:
        folder.mkdir()  # fails if the folder exists, even if its SKILL.md didn't load
    except FileExistsError:
        raise SkillExistsError(f"A skill folder named '{name}' already exists.") from None

    frontmatter = yaml.safe_dump(
        {"name": name, "description": description},
        sort_keys=False,
        allow_unicode=True,
        width=1_000_000,
    )
    skill_md = folder / "SKILL.md"
    try:
        skill_md.write_text(f"---\n{frontmatter}---\n\n{instructions}\n", encoding="utf-8")
        # Register exactly what's on disk, so a restart loads the same skill.
        skill = _parse_skill_md(skill_md)
    except Exception:
        shutil.rmtree(folder, ignore_errors=True)
        raise

    _skills[skill["name"]] = skill
    logger.info("Created skill %s", name)
    return {"name": skill["name"], "description": skill["description"]}


load_skills()
