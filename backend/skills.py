"""Load Agent Skills (https://agentskills.io) from the skills/ folder.

A skill is a folder containing a SKILL.md file: YAML frontmatter with at least
`name` and `description`, followed by markdown instructions.

    skills/
      code-review/
        SKILL.md

Skills are scanned once when this module is imported; call load_skills() to rescan.
"""

import logging
import re
from pathlib import Path

import yaml

SKILLS_DIR = Path(__file__).parent / "skills"

logger = logging.getLogger(__name__)

_FRONTMATTER_RE = re.compile(r"\A---[ \t]*\n(.*?)\n---[ \t]*(?:\n|\Z)(.*)\Z", re.DOTALL)

_skills: dict[str, dict] = {}


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


load_skills()
