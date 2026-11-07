from enum import StrEnum


class Role(StrEnum):
    BUYER = "buyer"
    MERCHANT = "merchant"
    TAILOR = "tailor"
    ADMIN = "admin"


class RoleStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    SUSPENDED = "suspended"


class UserStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"


class JobStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    COMPLETED_WITH_WARNINGS = "completed_with_warnings"
    FAILED = "failed"


class FileVisibility(StrEnum):
    PRIVATE = "private"
    PUBLIC = "public"
