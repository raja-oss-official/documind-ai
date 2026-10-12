# ============================================================
# IMPORTS
# ============================================================

from pymongo import MongoClient


from app.core.config import settings


# ============================================================
# MONGODB CONNECTION
# ============================================================

client = MongoClient(
    settings.mongodb_url
)


db = client[
    settings.database_name
]


# ============================================================
# USERS INDEXES
# ============================================================

# Every user must have a unique email address.
#
# This works together with the email normalization
# in auth.py.
db.users.create_index(
    "email",
    unique=True
)


# ============================================================
# REFRESH TOKEN INDEXES
# ============================================================

# Quickly find a refresh token using its hash.
#
# Each refresh token must have a unique hash.
db.refresh_tokens.create_index(
    "token_hash",
    unique=True
)


# Automatically remove expired refresh-token
# records from MongoDB.
#
# This is only database cleanup.
# Revocation is still handled by revoked_at.
db.refresh_tokens.create_index(
    "expires_at",
    expireAfterSeconds=0
)


# Quickly find all refresh tokens belonging
# to a particular user.
db.refresh_tokens.create_index(
    "user_id"
)


# ============================================================
# DOCUMENT INDEXES
# ============================================================

# Most document queries are scoped by user_id.
#
# This makes operations such as:
#
#   "List my documents"
#   "Find my document"
#   "Delete my document"
#
# faster.
db.documents.create_index(
    "user_id"
)


# Frequently used when retrieving documents
# belonging to a particular user in creation order.
#
# This supports:
#
#   user_id + created_at
#
# for the document listing endpoint.
db.documents.create_index(
    [
        ("user_id", 1),
        ("created_at", -1),
    ]
)


# ============================================================
# DOCUMENT CHUNK INDEXES
# ============================================================

# Chunks are frequently retrieved using:
#
#   document_id + user_id
#
# This protects the query pattern from becoming
# increasingly expensive as the number of chunks grows.
db.document_chunks.create_index(
    [
        ("document_id", 1),
        ("user_id", 1),
    ]
)


# Useful when searching chunks belonging to
# a particular user.
db.document_chunks.create_index(
    "user_id"
)


# ============================================================
# CHAT SESSION INDEXES
# ============================================================

# Chat sessions are always user-scoped.
#
# This supports:
#
#   "List my chats"
#   "Find my chat"
#   "Update my chat"
#   "Delete my chat"
db.chat_sessions.create_index(
    "user_id"
)


# Chat lists are normally displayed with the
# newest chats first.
#
# This supports:
#
#   user_id + updated_at
#
db.chat_sessions.create_index(
    [
        ("user_id", 1),
        ("updated_at", -1),
    ]
)


# ============================================================
# CHAT MESSAGE INDEXES
# ============================================================

# Messages are retrieved by:
#
#   session_id + user_id
#
# This makes loading a chat's conversation
# history much faster.
db.chat_messages.create_index(
    [
        ("session_id", 1),
        ("user_id", 1),
    ]
)


# Sort messages chronologically within
# a particular chat session.
#
# This supports:
#
#   session_id + created_at
#
db.chat_messages.create_index(
    [
        ("session_id", 1),
        ("created_at", 1),
    ]
)


# ============================================================
# DATABASE CONNECTION TEST
# ============================================================

# Ping MongoDB when the application starts.
#
# If MongoDB is unavailable, the application will
# immediately report the connection problem instead
# of silently continuing.
client.admin.command(
    "ping"
)