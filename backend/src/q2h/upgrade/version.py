"""Version parsing and comparison for MAJOR.EVOLUTION.MINOR.BUILD format."""


def parse_version(version_str: str) -> tuple[int, ...]:
    """Parse version string '1.1.11.1' into a tuple of ints.

    Accepts optional 'v' prefix and surrounding whitespace.
    Raises ValueError if format is invalid.
    """
    cleaned = version_str.strip().lstrip("v")
    parts = cleaned.split(".")
    if len(parts) != 4:
        raise ValueError(
            f"Invalid version format: '{version_str}' "
            f"(expected MAJOR.EVOLUTION.MINOR.BUILD, got {len(parts)} segments)"
        )
    try:
        return tuple(int(p) for p in parts)
    except ValueError:
        raise ValueError(f"Invalid version format: '{version_str}' (non-numeric segment)")


def is_newer(candidate: str, current: str) -> bool:
    """Return True if candidate version is strictly greater than current."""
    return parse_version(candidate) > parse_version(current)
