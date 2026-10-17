"""Create an untracked local environment without exposing generated secrets."""

from secrets import token_urlsafe

from app.config import ROOT


def main():
    """Create .env only when it does not already exist."""
    # Pre-create bind sources as the host user; Docker would otherwise create root-owned paths on Linux.
    for folder in ("data", "artifacts"):
        (ROOT / folder).mkdir(parents=True, exist_ok=True)
    path = ROOT / ".env"
    if path.exists():
        print("Existing .env preserved")
        return
    text = (ROOT / ".env.example").read_text()
    text = text.replace("NEO4J_PASSWORD=replace_with_local_secret", "NEO4J_PASSWORD=" + token_urlsafe(24))
    text = text.replace("APP_API_KEY=replace_with_local_secret", "APP_API_KEY=" + token_urlsafe(32))
    path.write_text(text)
    path.chmod(0o600)
    print("Created local .env with unique secrets. Values were not printed.")


if __name__ == "__main__":
    main()
