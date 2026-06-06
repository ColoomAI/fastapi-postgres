"""bcrypt password hashing.

10 rounds = ~80ms on modern hardware — bcrypt's default and a
reasonable throughput/security trade for an API used by humans (not an
OAuth service hashing millions of times). Bumping linearly increases
the per-login cost.
"""
import bcrypt

ROUNDS = 10


def hash_password(plain: str) -> str:
    """Return the bcrypt digest. Output is a self-describing string
    that includes algo + cost + salt — no need to store anything else
    alongside it."""
    digest = bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(ROUNDS))
    return digest.decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Constant-time compare via bcrypt's own check. Returns False on
    any error (malformed hash, etc.) rather than raising, so caller
    code can stay symmetric to the happy path."""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False
