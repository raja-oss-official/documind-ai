import re

from fastapi import (
    APIRouter,
    HTTPException,
    Depends,
    Request,
)

from bson import ObjectId
from pymongo.errors import DuplicateKeyError
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.schemas.user import (
    UserCreate,
    UserLogin,
    PasswordChangeRequest,
)

from app.core.database import db

from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    verify_refresh_token,
    security,
    verify_access_token,
)

from app.services.refresh_token_service import (
    create_refresh_token_record,
    is_refresh_token_active,
    revoke_refresh_token,
    revoke_all_user_refresh_tokens,
)


router = APIRouter()


# -------------------------------------------------
# Rate Limiter
# -------------------------------------------------

limiter = Limiter(
    key_func=get_remote_address
)


# -------------------------------------------------
# Email Normalization
# -------------------------------------------------

def normalize_email(email: str) -> str:
    """
    Normalize an email address.
    """

    return email.strip().lower()


# -------------------------------------------------
# Password Strength Validation
# -------------------------------------------------

def validate_password_strength(password: str):
    """
    Validate password security requirements.
    """

    if len(password) < 8:
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 8 characters long",
        )

    if not re.search(r"[A-Z]", password):
        raise HTTPException(
            status_code=400,
            detail="Password must contain at least one uppercase letter",
        )

    if not re.search(r"[a-z]", password):
        raise HTTPException(
            status_code=400,
            detail="Password must contain at least one lowercase letter",
        )

    if not re.search(r"\d", password):
        raise HTTPException(
            status_code=400,
            detail="Password must contain at least one number",
        )

    if not re.search(r"[^A-Za-z0-9]", password):
        raise HTTPException(
            status_code=400,
            detail="Password must contain at least one special character",
        )


# -------------------------------------------------
# Register
# -------------------------------------------------

@router.post("/register")
@limiter.limit("5/minute")
def register_user(
    request: Request,
    user: UserCreate,
):

    email = normalize_email(
        user.email
    )

    # Validate password strength.
    validate_password_strength(
        user.password
    )

    # Check whether the email already exists.
    existing_user = db.users.find_one(
        {
            "email": email
        }
    )

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Email already registered",
        )

    # Create user document.
    new_user = {
        "name": user.name.strip(),
        "email": email,
        "password_hash": hash_password(
            user.password
        ),
    }

    try:

        result = db.users.insert_one(
            new_user
        )

    except DuplicateKeyError:

        # Handles the race condition where
        # another request creates the same email
        # between find_one() and insert_one().
        raise HTTPException(
            status_code=400,
            detail="Email already registered",
        )

    return {
        "message": "User registered successfully",
        "user_id": str(
            result.inserted_id
        ),
    }


# -------------------------------------------------
# Login
# -------------------------------------------------

@router.post("/login")
@limiter.limit("5/minute")
def login_user(
    request: Request,
    user: UserLogin,
):

    email = normalize_email(
        user.email
    )

    # Find user.
    existing_user = db.users.find_one(
        {
            "email": email
        }
    )

    if not existing_user:

        raise HTTPException(
            status_code=401,
            detail="Invalid email or password",
        )

    # Verify password.
    password_valid = verify_password(
        user.password,
        existing_user["password_hash"],
    )

    if not password_valid:

        raise HTTPException(
            status_code=401,
            detail="Invalid email or password",
        )

    user_id = str(
        existing_user["_id"]
    )

    # Create access token.
    access_token = create_access_token(
        user_id
    )

    # Create refresh token.
    refresh_token = create_refresh_token(
        user_id
    )

    # Extract refresh-token expiration.
    refresh_token_data = verify_refresh_token(
        refresh_token
    )

    # Store hashed refresh token.
    create_refresh_token_record(
        user_id=user_id,
        refresh_token=refresh_token,
        expires_at=refresh_token_data[
            "expires_at"
        ],
    )

    return {
        "message": "Login successful",
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


# -------------------------------------------------
# Refresh Access Token
# -------------------------------------------------

@router.post("/refresh")
@limiter.limit("10/minute")
def refresh_access_token(
    request: Request,
    refresh_token: str,
):

    # Verify JWT structure and expiration.
    refresh_token_data = verify_refresh_token(
        refresh_token
    )

    user_id = refresh_token_data[
        "user_id"
    ]

    # Check whether the refresh token
    # still exists and has not been revoked.
    if not is_refresh_token_active(
        refresh_token
    ):

        raise HTTPException(
            status_code=401,
            detail="Refresh token has been revoked or expired",
        )

    # Validate user ID.
    if not ObjectId.is_valid(
        user_id
    ):

        raise HTTPException(
            status_code=401,
            detail="Invalid refresh token",
        )

    # Make sure the user still exists.
    user = db.users.find_one(
        {
            "_id": ObjectId(user_id)
        }
    )

    if not user:

        raise HTTPException(
            status_code=401,
            detail="User not found",
        )

    # -------------------------------------------------
    # Refresh Token Rotation
    # -------------------------------------------------

    # Revoke the old refresh token.
    revoke_refresh_token(
        refresh_token
    )

    # Create new access token.
    new_access_token = create_access_token(
        user_id
    )

    # Create new refresh token.
    new_refresh_token = create_refresh_token(
        user_id
    )

    # Extract expiration.
    new_refresh_token_data = verify_refresh_token(
        new_refresh_token
    )

    # Store new refresh token.
    create_refresh_token_record(
        user_id=user_id,
        refresh_token=new_refresh_token,
        expires_at=new_refresh_token_data[
            "expires_at"
        ],
    )

    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
    }


# -------------------------------------------------
# Logout
# -------------------------------------------------

@router.post("/logout")
def logout_user(
    refresh_token: str,
):

    # Verify that the JWT itself is valid.
    verify_refresh_token(
        refresh_token
    )

    # Revoke the refresh token.
    revoked = revoke_refresh_token(
        refresh_token
    )

    if not revoked:

        raise HTTPException(
            status_code=401,
            detail=(
                "Refresh token is already "
                "revoked or does not exist"
            ),
        )

    return {
        "message": "Logout successful"
    }


# -------------------------------------------------
# Change Password
# -------------------------------------------------

@router.post("/change-password")
@limiter.limit("5/minute")
def change_password(
    request: Request,
    password_request: PasswordChangeRequest,
    credentials=Depends(security),
):

    # Verify access token.
    user_id = verify_access_token(
        credentials
    )

    # Validate user ID.
    if not ObjectId.is_valid(
        user_id
    ):

        raise HTTPException(
            status_code=401,
            detail="Invalid user ID",
        )

    # Find user.
    user = db.users.find_one(
        {
            "_id": ObjectId(user_id)
        }
    )

    if not user:

        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    # -------------------------------------------------
    # Verify Current Password
    # -------------------------------------------------

    if not verify_password(
        password_request.current_password,
        user["password_hash"],
    ):

        raise HTTPException(
            status_code=400,
            detail="Current password is incorrect",
        )

    # -------------------------------------------------
    # Validate New Password
    # -------------------------------------------------

    validate_password_strength(
        password_request.new_password
    )

    # -------------------------------------------------
    # Prevent Password Reuse
    # -------------------------------------------------

    if verify_password(
        password_request.new_password,
        user["password_hash"],
    ):

        raise HTTPException(
            status_code=400,
            detail=(
                "New password must be different "
                "from the current password"
            ),
        )

    # -------------------------------------------------
    # Hash New Password
    # -------------------------------------------------

    new_password_hash = hash_password(
        password_request.new_password
    )

    # -------------------------------------------------
    # Update Password
    # -------------------------------------------------

    db.users.update_one(
        {
            "_id": ObjectId(user_id)
        },
        {
            "$set": {
                "password_hash": new_password_hash
            }
        },
    )

    # -------------------------------------------------
    # Revoke Existing Refresh Tokens
    # -------------------------------------------------

    revoke_all_user_refresh_tokens(
        user_id
    )

    return {
        "message": (
            "Password changed successfully. "
            "Please log in again."
        )
    }


# -------------------------------------------------
# Get Current User
# -------------------------------------------------

@router.get("/me")
def get_current_user(
    credentials=Depends(security),
):

    # Verify access token.
    user_id = verify_access_token(
        credentials
    )

    # Validate user ID.
    if not ObjectId.is_valid(
        user_id
    ):

        raise HTTPException(
            status_code=401,
            detail="Invalid user ID",
        )

    # Find user.
    user = db.users.find_one(
        {
            "_id": ObjectId(user_id)
        }
    )

    if not user:

        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    return {
        "id": str(
            user["_id"]
        ),
        "name": user["name"],
        "email": user["email"],
    }