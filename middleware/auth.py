from fastapi import HTTPException, Request, status


async def validate_api_key(request: Request) -> None:
    api_key = request.headers.get("X-API-Key")
    expected = getattr(request.app.state.settings, "api_keys", "")
    allowed_keys = {key.strip() for key in expected.split(",") if key.strip()}
    if not api_key or api_key not in allowed_keys:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key.",
        )
