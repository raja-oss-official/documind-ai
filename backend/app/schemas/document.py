# ============================================================
# IMPORTS
# ============================================================

from datetime import datetime
from typing import Literal

from pydantic import (
    BaseModel,
    EmailStr,
    ConfigDict,
    Field,
    field_validator,
)


# -------------------------------------------------
# Shared Document Schema Configuration
# -------------------------------------------------

class DocumentBase(BaseModel):

    model_config = ConfigDict(
        extra="forbid"
    )


# -------------------------------------------------
# Document Response
# -------------------------------------------------

class DocumentResponse(DocumentBase):

    id: str

    user_id: str

    filename: str

    file_type: str

    file_size: int = Field(
        ...,
        ge=0,
    )

    status: str

    created_at: datetime


# -------------------------------------------------
# Document Question
# -------------------------------------------------

class QuestionRequest(DocumentBase):

    question: str = Field(
        ...,
        min_length=1,
        max_length=5000,
    )

    document_id: str | None = Field(
        default=None,
        max_length=100,
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


# -------------------------------------------------
# Document Rename
# -------------------------------------------------

class DocumentRenameRequest(DocumentBase):

    filename: str = Field(
        ...,
        min_length=1,
        max_length=255,
    )

    @field_validator("filename")
    @classmethod
    def validate_filename(
        cls,
        value: str,
    ) -> str:

        value = value.strip()

        if not value:
            raise ValueError(
                "Filename cannot be empty"
            )

        return value

# -------------------------------------------------
# Compare Two Documents
# -------------------------------------------------

class CompareRequest(DocumentBase):

    document_ids: list[str] = Field(
        ...,
        min_length=2,
        max_length=2,
    )

    focus: str | None = Field(
        default=None,
        max_length=500,
    )

    @field_validator("document_ids")
    @classmethod
    def validate_document_ids(
        cls,
        value: list[str],
    ) -> list[str]:

        value = [
            document_id.strip()
            for document_id in value
        ]

        if len(set(value)) != 2:
            raise ValueError(
                "Choose two different documents"
            )

        return value


# -------------------------------------------------
# Quiz / Flashcards
# -------------------------------------------------

class StudyRequest(DocumentBase):

    type: Literal["quiz", "flashcards"] = "quiz"

    count: int = Field(
        default=8,
        ge=3,
        le=15,
    )


# -------------------------------------------------
# Share a Document or Chat
# -------------------------------------------------

class ShareRequest(DocumentBase):

    email: EmailStr

    role: Literal["viewer", "editor"] = "viewer"


# -------------------------------------------------
# Add a YouTube Video
# -------------------------------------------------

class YouTubeRequest(DocumentBase):

    url: str = Field(
        ...,
        min_length=5,
        max_length=500,
    )
