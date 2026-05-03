from fastapi import Request


def accepts_json(request: Request) -> bool:
    """Return True when the client explicitly requests JSON via the Accept header."""
    return "application/json" in request.headers.get("accept", "")
