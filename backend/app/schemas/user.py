from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
)


# -------------------------------------------------
# Shared User Schema Configuration
# -------------------------------------------------

class UserBase(BaseModel):

    model_config = ConfigDict(
        extra="forbid"
    )


# -------------------------------------------------
# User Registration
# -------------------------------------------------

class UserCreate(UserBase):

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
    )

    email: EmailStr

    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:

        value = value.strip()

        if not value:
            raise ValueError(
                "Name cannot be empty"
            )

        return value


# -------------------------------------------------
# User Login
# -------------------------------------------------

class UserLogin(UserBase):

    email: EmailStr

    password: str = Field(
        ...,
        min_length=1,
        max_length=128,
    )


# -------------------------------------------------
# Password Change
# -------------------------------------------------

class PasswordChangeRequest(UserBase):

    current_password: str = Field(
        ...,
        min_length=1,
        max_length=128,
    )

    new_password: str = Field(
        ...,
        min_length=8,
        max_length=128,
    )