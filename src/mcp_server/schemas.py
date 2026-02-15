from pydantic import BaseModel


class ToolRequest(BaseModel):
    tool: str
    args: dict


class ToolResponse(BaseModel):
    success: bool
    result: dict | list | str | None = None
    error: str | None = None
