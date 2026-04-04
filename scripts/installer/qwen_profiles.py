"""Scan ~/.qwen-accounts for Qwen Code profiles."""

import os
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ProfileInfo:
    """Information about a detected Qwen profile."""
    name: str           # Directory basename, used as --profile value
    display_name: str   # Human-readable name
    path: Path          # Full path to profile directory
    oauth_active: bool  # Whether oauth_creds.json exists


# Known display name overrides for common profiles
_KNOWN_NAMES = {
    "mitchelbaker": "Mitchel",
    "adalovelace": "Ada Lovelace",
}


def _title_case_with_exceptions(slug: str) -> str:
    """Convert slug to title case with special handling."""
    if slug in _KNOWN_NAMES:
        return _KNOWN_NAMES[slug]

    # If already contains spaces, return as-is (preserve user formatting)
    if ' ' in slug:
        return slug

    # Try simple title case
    title = slug.title()

    # Handle camelCase by inserting spaces before capitals
    spaced = re.sub(r'([A-Z])', r' \1', slug[0].upper() + slug[1:]).strip()

    # Return whichever looks more readable
    return spaced if ' ' in spaced else title


def get_profile_display_name(slug: str) -> str:
    """Convert a profile directory name to a display name.

    Args:
        slug: Directory name (e.g., "adalovelace", "mitchelbaker")

    Returns:
        Human-readable name (e.g., "Ada Lovelace", "Mitchel")
    """
    return _title_case_with_exceptions(slug)


def check_oauth_status(profile_path: Path) -> bool:
    """Check if a profile has active OAuth credentials.

    Args:
        profile_path: Path to the profile directory

    Returns:
        True if oauth_creds.json exists, False otherwise
    """
    return (profile_path / "oauth_creds.json").exists()


def scan_qwen_accounts() -> list[ProfileInfo]:
    """Scan ~/.qwen-accounts for available Qwen profiles.

    Returns:
        List of ProfileInfo objects, sorted by display name
    """
    accounts_dir = Path(os.environ.get(
        "QWEN_ACCOUNTS_DIR",
        Path.home() / ".qwen-accounts"
    ))

    if not accounts_dir.is_dir():
        return []

    profiles = []
    for entry in sorted(accounts_dir.iterdir()):
        if entry.is_dir():
            profiles.append(ProfileInfo(
                name=entry.name,
                display_name=get_profile_display_name(entry.name),
                path=entry,
                oauth_active=check_oauth_status(entry),
            ))

    return profiles
