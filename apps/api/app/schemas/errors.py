from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    field: str | None = Field(default=None, description="Form field the error relates to.")
    message: str


class ErrorBody(BaseModel):
    code: str = Field(description="Stable, machine-readable error code.")
    message: str = Field(description="Human-readable summary safe to show to farmers.")
    details: list[ErrorDetail] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    error: ErrorBody
