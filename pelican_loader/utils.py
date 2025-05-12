import string


def sanitize_name(name: str) -> str:
    """Sanitize a string to be a valid filename by replacing invalid characters with '_'."""
    valid_chars = string.ascii_letters + string.digits + "-_."
    return "".join(c if c in valid_chars else "_" for c in name)
