from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Table
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from database import Base

# Связь документ <-> метки
doc_tags = Table(
    "doc_tags", Base.metadata,
    Column("document_id", Integer, ForeignKey("documents.id", ondelete="CASCADE")),
    Column("tag_id", Integer, ForeignKey("tags.id", ondelete="CASCADE")),
)

# Связь документ <-> связанные документы
doc_related = Table(
    "doc_related", Base.metadata,
    Column("doc_id", Integer, ForeignKey("documents.id", ondelete="CASCADE")),
    Column("related_id", Integer, ForeignKey("documents.id", ondelete="CASCADE")),
)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    login = Column(String(20), unique=True, nullable=True, index=True)
    name = Column(String(200), nullable=False)
    email = Column(String(200), unique=True, nullable=False, index=True)
    password_hash = Column(String(200), nullable=False)
    role = Column(String(20), default="user")  # admin, manager, user
    department = Column(String(200), default="")
    position = Column(String(200), default="")
    color = Column(String(20), default="#2563eb")
    deputy_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    documents = relationship("Document", back_populates="author_user", foreign_keys="Document.author_id")
    deputy = relationship("User", remote_side="User.id", foreign_keys=[deputy_id])
    approvals = relationship("Approval", back_populates="user")
    comments = relationship("Comment", back_populates="user")
    notifications = relationship("Notification", back_populates="user")


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    number = Column(String(50), index=True)
    title = Column(String(500), nullable=False)
    description = Column(Text, default="")
    content = Column(Text, nullable=False)
    doc_type = Column(String(50), nullable=False)
    status = Column(String(20), default="draft")
    priority = Column(String(20), default="normal")
    sequential = Column(Boolean, default=False)
    deadline = Column(String(20), default="")
    extra_fields = Column(Text, default="{}")
    deleted = Column(Boolean, default=False)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    author_user = relationship("User", back_populates="documents", foreign_keys=[author_id])
    approvals = relationship("Approval", back_populates="document", cascade="all, delete-orphan")
    comments = relationship("Comment", back_populates="document", cascade="all, delete-orphan", order_by="Comment.created_at")
    history = relationship("History", back_populates="document", cascade="all, delete-orphan", order_by="History.created_at")
    versions = relationship("Version", back_populates="document", cascade="all, delete-orphan", order_by="Version.created_at")
    attachments = relationship("Attachment", back_populates="document", cascade="all, delete-orphan")
    tags = relationship("Tag", secondary=doc_tags, back_populates="documents")
    related_docs = relationship(
        "Document", secondary=doc_related,
        primaryjoin=id == doc_related.c.doc_id,
        secondaryjoin=id == doc_related.c.related_id,
    )


class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    color = Column(String(20), default="blue")

    documents = relationship("Document", secondary=doc_tags, back_populates="tags")


class Approval(Base):
    __tablename__ = "approvals"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(String(20), default="pending")  # pending, approved, rejected
    comment = Column(Text, default="")
    signature = Column(String(64), default="")
    order_num = Column(Integer, default=0)
    decided_at = Column(DateTime, nullable=True)

    document = relationship("Document", back_populates="approvals")
    user = relationship("User", back_populates="approvals")


class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    document = relationship("Document", back_populates="comments")
    user = relationship("User", back_populates="comments")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    notif_type = Column(String(50), default="info")
    title = Column(String(300), default="")
    message = Column(Text, default="")
    doc_id = Column(Integer, nullable=True)
    read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="notifications")


class History(Base):
    __tablename__ = "history"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    user_name = Column(String(200), default="")
    text = Column(Text, default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    document = relationship("Document", back_populates="history")


class Version(Base):
    __tablename__ = "versions"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(500), default="")
    content = Column(Text, default="")
    user_name = Column(String(200), default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    document = relationship("Document", back_populates="versions")


class Attachment(Base):
    __tablename__ = "attachments"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    filename = Column(String(500), nullable=False)
    filepath = Column(String(1000), default="")
    size = Column(String(50), default="")
    filesize = Column(Integer, default=0)

    document = relationship("Document", back_populates="attachments")


class ApprovalRoute(Base):
    __tablename__ = "approval_routes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    user_ids = Column(Text, default="")
    sequential = Column(Boolean, default=False)


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(500), nullable=False)
    description = Column(Text, default="")
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    assignee_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(String(20), default="pending")  # pending, in_progress, completed, cancelled
    priority = Column(String(20), default="medium")
    deadline = Column(String(20), default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    document = relationship("Document", foreign_keys=[document_id])
    author = relationship("User", foreign_keys=[author_id])
    assignee = relationship("User", foreign_keys=[assignee_id])
