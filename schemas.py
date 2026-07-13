from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional


# --- Auth ---
class UserRegister(BaseModel):
    name: str
    email: EmailStr
    password: str
    department: str = ""
    position: str = ""

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserOut(BaseModel):
    id: int
    name: str
    email: str
    role: str
    department: str
    position: str
    color: str
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
    size: str
    model_config = {"from_attributes": True}

class VersionOut(BaseModel):
    id: int
    title: str
    content: str
    user_name: str
    created_at: datetime
    model_config = {"from_attributes": True}

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
    name: str
    email: EmailStr
    password: str = "123456"
    role: str = "user"
    department: str = ""
    position: str = ""
