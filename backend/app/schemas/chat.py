# ============================================================
# IMPORTS
# ============================================================

from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)


# -------------------------------------------------
# Shared Chat Schema Configuration
# -------------------------------------------------

class ChatBase(BaseModel):

    model_config = ConfigDict(
        extra="forbid"
    )


# -------------------------------------------------
# Create Chat Session
# -------------------------------------------------

class ChatSessionCreate(ChatBase):

    title: str = Field(
        default="New Chat",
        min_length=1,
        max_length=200,
    )

    document_id: str | None = Field(
        default=None,
        max_length=100,
    )

    @field_validator("title")
    @classmethod
    def validate_title(
        cls,
        value: str,
    ) -> str:

        value = value.strip()

        if not value:
            raise ValueError(
                "Chat title cannot be empty"
            )

        return value


# -------------------------------------------------
# Update Chat Session
# -------------------------------------------------

class ChatSessionUpdate(ChatBase):

    title: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
    )

    document_id: str | None = Field(
        default=None,
        max_length=100,
    )

    @field_validator("title")
    @classmethod
    def validate_title(
        cls,
        value: str | None,
    ) -> str | None:

        if value is None:
            return None

        value = value.strip()

        if not value:
            raise ValueError(
                "Chat title cannot be empty"
            )

        return value


# -------------------------------------------------
# Chat Session Response
# -------------------------------------------------

class ChatSessionResponse(ChatBase):

    id: str

    user_id: str

    title: str

    document_id: str | None

    created_at: datetime

    updated_at: datetime


# -------------------------------------------------
# Create Chat Message
# -------------------------------------------------

class ChatMessageCreate(ChatBase):

    content: str = Field(
        ...,
        min_length=1,
        max_length=10000,
    )

    @field_validator("content")
    @classmethod
    def validate_content(
        cls,
        value: str,
    ) -> str:

        value = value.strip()

        if not value:
            raise ValueError(
                "Message content cannot be empty"
            )

        return value


# -------------------------------------------------
# Chat Message Response
# -------------------------------------------------

class ChatMessageResponse(ChatBase):

    id: str

    session_id: str

    user_id: str

    role: str

    content: str

    document_id: str | None

    created_at: datetime


# -------------------------------------------------
# Chat Question
# -------------------------------------------------

class ChatQuestionRequest(ChatBase):

    question: str = Field(
        ...,
        min_length=1,
        max_length=5000,
    )

    @field_validator("question")
    @classmethod
    def validate_question(
        cls,
        value: str,
    ) -> str:

        value = value.strip()

        if not value:
            raise ValueError(
                "Question cannot be empty"
            )

        return value