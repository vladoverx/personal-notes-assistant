from __future__ import annotations


def validate_password_strength(password: str) -> tuple[bool, str | None]:
    """Validate password strength."""
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"

    weak_passwords = {"password", "123456", "qwerty", "admin", "test", "password123"}
    if password.lower() in weak_passwords:
        return False, "Password is too weak. Please choose a stronger password."
    return True, None
