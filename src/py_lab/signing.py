from __future__ import annotations

import hashlib
import hmac


def sign(key:str, message:str) -> str:
    """Generate a HMAC-SHA256 signature for the given message using the provided key."""
    mac = hmac.new(key.encode("utf-8"), message.encode("utf-8"), hashlib.sha256)
    return mac.hexdigest()

def constant_time_eq(a:str, b:str) -> bool:
    """Compare two strings in constant time to prevent timing attacks."""
    return hmac.compare_digest(a, b)
