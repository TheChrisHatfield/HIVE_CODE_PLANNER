"""GitHub authentication provider."""

from __future__ import annotations

from .base import AuthProvider


class GitHubAuth(AuthProvider):
    """GitHub authentication provider.

    Supports the ``bearer`` auth scheme, used for PATs, fine-grained PATs,
    OAuth tokens, and GitHub App installation tokens.
    """

    key = "github"
    supported_auth_schemes = ("bearer",)

    def auth_headers(self, token: str, auth_scheme: str) -> dict[str, str]:
        """Return ``Authorization: Bearer <token>``."""
        if auth_scheme != "bearer":
            raise ValueError(
                f"GitHubAuth does not support auth scheme {auth_scheme!r}"
            )
        credential = token.strip()
        lowered = credential.casefold()
        if lowered.startswith("bearer "):
            credential = credential[7:].strip()
        elif lowered.startswith("token "):
            credential = credential[6:].strip()
        return {"Authorization": f"Bearer {credential}"}
