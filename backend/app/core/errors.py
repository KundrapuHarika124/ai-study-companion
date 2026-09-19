from fastapi import HTTPException


class NotFound(HTTPException):
    def __init__(self, what: str = "Resource"):
        super().__init__(status_code=404, detail=f"{what} not found")


class Forbidden(HTTPException):
    def __init__(self, detail: str = "Not allowed"):
        super().__init__(status_code=403, detail=detail)


class BadRequest(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=400, detail=detail)


class AIUnavailable(HTTPException):
    def __init__(self, detail: str = "AI provider is not configured or unavailable. Set GEMINI_API_KEY and retry."):
        super().__init__(status_code=503, detail=detail)


class Conflict(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=409, detail=detail)
