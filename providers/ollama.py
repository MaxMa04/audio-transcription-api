class OllamaWhisperProvider:
    def __init__(self, base_url: str, model: str, timeout_seconds: float) -> None:
        self.base_url = base_url
        self.model = model
        self.timeout_seconds = timeout_seconds

    async def healthcheck(self) -> bool:
        return True
