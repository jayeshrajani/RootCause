from pydantic import BaseModel, Field


class TranscriptionResponse(BaseModel):
    transcript: str = Field(description="Recognised text in the spoken language (not translated).")
    language: str = Field(description="Language code used for recognition, e.g. hi-IN.")
