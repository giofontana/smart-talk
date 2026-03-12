"""REST request/response models for the Smart Talk Agent API."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ConversationRequest(BaseModel):
    """Incoming POST /conversation request body."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "session_id": "session-abc123",
                "text": "Turn on the kitchen light at 70% brightness.",
                "language": "en",
            }
        }
    )

    session_id: str = Field(..., description="Unique conversation session identifier.")
    text: str = Field(..., description="User's natural language input.")
    language: str = Field(default="en", description="BCP-47 language tag of the input text.")


class ConversationResponse(BaseModel):
    """Outgoing POST /conversation response body."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "session_id": "session-abc123",
                "text": "Done! Kitchen Light is now on at 70% brightness.",
                "language": "en",
            }
        }
    )

    session_id: str = Field(..., description="Echo of the request session_id.")
    text: str = Field(..., description="Agent's natural language response.")
    language: str = Field(default="en", description="BCP-47 language tag of the response text.")
