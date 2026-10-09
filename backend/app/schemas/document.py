from datetime import datetime

from pydantic import (
    BaseModel,
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