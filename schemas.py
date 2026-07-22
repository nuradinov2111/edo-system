from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Any


# --- Auth ---
class UserRegister(BaseModel):
    login: str
    name: str
    password: str
    department: str = ""
    position: str = ""

class UserLogin(BaseModel):
    login: str
    password: str

class UserOut(BaseModel):
    id: int
    login: Optional[str] = ""
    name: str
    email: str
    role: str
    department: str
    position: str
    color: str
    deputy_id: Optional[int] = None
    user_status: str = "available"
    notify_email: str = ""
    notify_telegram: str = ""
    notify_browser: bool = True
    notify_on_approve: bool = True
    notify_on_reject: bool = True
    notify_on_comment: bool = True
    notify_on_task: bool = True
    model_config = {"from_attributes": True}

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# --- Document ---
class DocumentCreate(BaseModel):
    title: str
    description: str = ""
    content: str = ""
    doc_type: str
    status: str = "draft"
    priority: str = "normal"
    sequential: bool = False
    deadline: str = ""
    extra_fields: dict[str, Any] = {}
    approver_ids: list[int] = []
    tag_ids: list[int] = []
    related_doc_ids: list[int] = []
    attachments: list[dict] = []

class ApprovalOut(BaseModel):
    id: int
    user_id: int
    user_name: str = ""
    status: str
    comment: str
    signature: str
    order_num: int
    decided_at: Optional[datetime] = None
    model_config = {"from_attributes": True}

class CommentOut(BaseModel):
    id: int
    user_id: int
    user_name: str = ""
    text: str
    created_at: datetime
    model_config = {"from_attributes": True}

class HistoryOut(BaseModel):
    id: int
    user_name: str
    text: str
    created_at: datetime
    model_config = {"from_attributes": True}

class TagOut(BaseModel):
    id: int
    name: str
    color: str
    model_config = {"from_attributes": True}

class AttachmentOut(BaseModel):
    id: int
    filename: str
    filepath: str = ""
    size: str
    filesize: int = 0
    model_config = {"from_attributes": True}

class VersionOut(BaseModel):
    id: int
    title: str
    content: str
    user_name: str
    created_at: datetime
    model_config = {"from_attributes": True}

class ResolutionOut(BaseModel):
    id: int
    user_id: int
    user_name: str = ""
    text: str
    created_at: datetime
    model_config = {"from_attributes": True}

class ResolutionCreate(BaseModel):
    text: str


class DocumentOut(BaseModel):
    id: int
    number: str
    title: str
    description: str
    content: str
    doc_type: str
    status: str
    priority: str
    sequential: bool
    deadline: str
    extra_fields: dict[str, Any] = {}
    deleted: bool = False
    author_id: int
    author_name: str = ""
    created_at: datetime
    updated_at: datetime
    approvals: list[ApprovalOut] = []
    comments: list[CommentOut] = []
    history: list[HistoryOut] = []
    versions: list[VersionOut] = []
    attachments: list[AttachmentOut] = []
    tags: list[TagOut] = []
    related_doc_ids: list[int] = []
    resolution: Optional[ResolutionOut] = None
    model_config = {"from_attributes": True}


# --- Notification ---
class NotificationOut(BaseModel):
    id: int
    notif_type: str
    title: str
    message: str
    doc_id: Optional[int] = None
    read: bool
    created_at: datetime
    model_config = {"from_attributes": True}


# --- Comment ---
class CommentCreate(BaseModel):
    text: str


# --- Approval action ---
class ApprovalAction(BaseModel):
    comment: str = ""
    pin: str = ""


# --- Route ---
class RouteCreate(BaseModel):
    name: str
    user_ids: list[int]
    sequential: bool = False

class RouteOut(BaseModel):
    id: int
    name: str
    user_ids: str
    sequential: bool
    model_config = {"from_attributes": True}


# --- User management ---
class UserCreate(BaseModel):
    login: str
    name: str
    password: str = "123456"
    role: str = "user"
    department: str = ""
    position: str = ""
    deputy_id: Optional[int] = None


class DeputySet(BaseModel):
    deputy_id: Optional[int] = None


class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    department: Optional[str] = None
    position: Optional[str] = None
    user_status: Optional[str] = None
    notify_email: Optional[str] = None
    notify_telegram: Optional[str] = None
    notify_browser: Optional[bool] = None
    notify_on_approve: Optional[bool] = None
    notify_on_reject: Optional[bool] = None
    notify_on_comment: Optional[bool] = None
    notify_on_task: Optional[bool] = None


class PasswordChange(BaseModel):
    old_password: str
    new_password: str


# --- Task (поручение) ---
class TaskCreate(BaseModel):
    title: str
    description: str = ""
    document_id: Optional[int] = None
    assignee_id: int
    priority: str = "medium"
    deadline: str = ""

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    deadline: Optional[str] = None

class UserOutPublic(BaseModel):
    """Limited user info for non-admin users (no login/email)."""
    id: int
    name: str
    role: str
    department: str
    position: str
    color: str
    deputy_id: Optional[int] = None
    model_config = {"from_attributes": True}


class TaskOut(BaseModel):
    id: int
    title: str
    description: str
    document_id: Optional[int] = None
    author_id: int
    author_name: str = ""
    assignee_id: int
    assignee_name: str = ""
    status: str
    priority: str
    deadline: str
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


# --- Audit Log ---
class AuditLogOut(BaseModel):
    id: int
    user_id: int
    user_name: str = ""
    action: str
    entity_type: str
    entity_id: Optional[int] = None
    details: str
    ip_address: str = ""
    created_at: datetime
    model_config = {"from_attributes": True}


# --- Document Template ---
class TemplateCreate(BaseModel):
    name: str
    doc_type: str
    title_template: str = ""
    description_template: str = ""
    content_template: str = ""
    extra_fields_template: dict[str, Any] = {}
    priority: str = "normal"
    approver_ids: list[int] = []
    sequential: bool = False
    is_public: bool = True

class TemplateOut(BaseModel):
    id: int
    name: str
    doc_type: str
    title_template: str
    description_template: str
    content_template: str
    extra_fields_template: dict[str, Any] = {}
    priority: str
    approver_ids: str = ""
    sequential: bool
    author_id: int
    author_name: str = ""
    is_public: bool
    created_at: datetime
    model_config = {"from_attributes": True}


# --- Bulk operations ---
class BulkAction(BaseModel):
    doc_ids: list[int]
    action: str  # delete, archive, restore


# --- Nomenclature ---
class NomenclatureCaseCreate(BaseModel):
    index: str
    title: str
    department: str = ""
    retention_years: int = 5
    description: str = ""

class NomenclatureCaseOut(BaseModel):
    id: int
    index: str
    title: str
    department: str
    retention_years: int
    description: str
    created_at: datetime
    doc_count: int = 0
    model_config = {"from_attributes": True}
