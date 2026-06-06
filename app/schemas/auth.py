from pydantic import BaseModel, EmailStr, Field


class Credentials(BaseModel):
    """Inbound shape for POST /api/auth/register + POST /api/auth/login.
    Length caps deliberately aggressive: ≥8 char password, ≤200 char to
    rule out a paste-the-whole-document mistake."""

    email: EmailStr = Field(max_length=254)
    password: str = Field(min_length=8, max_length=200)


class UserPublic(BaseModel):
    """User shape safe to return in responses. NEVER add password_hash
    here — that's how a refactor accidentally ships the hash to the
    client. Keep this thin and add server-side augmentation (role, plan,
    flags) as needed."""

    id: str
    email: str
