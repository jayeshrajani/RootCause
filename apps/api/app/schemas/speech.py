from pydantic import BaseModel, Field

# About a minute of speech: enough for the summary, urgency and the first few actions.
SPEAK_MAX_CHARACTERS = 1200


class SpeakRequest(BaseModel):
    text: str = Field(
        min_length=1,
        max_length=SPEAK_MAX_CHARACTERS,
        description="Text to read aloud, in the language it should be spoken in.",
    )
