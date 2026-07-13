import os
from datetime import datetime, timezone
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, joinedload
from database import engine, get_db, Base
from models import (
    User, Document, Tag, Approval, Comment, Notification,
    History, Version, Attachment, ApprovalRoute, doc_tags, doc_related,
)
from schemas import (
    UserRegister, UserLogin, UserOut, Token, UserCreate,
    DocumentCreate, DocumentOut, ApprovalOut, CommentOut, CommentCreate,
    ApprovalAction, NotificationOut, RouteCreate, RouteOut, TagOut,
)
from auth import hash_password, verify_password, create_token, get_current_user
import secrets

app = FastAPI(title="ЭДО API")

# --- Startup ---
@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    db = next(get_db())
    # Создаем метки если их нет
    if db.query(Tag).count() == 0:
        for name, color in [("Срочно","red"),("Финансы","green"),("Кадры","blue"),("Продажи","yellow"),("Важно","purple"),("Личное","pink")]:
            db.add(Tag(name=name, color=color))
        db.commit()
    db.close()


# ============ AUTH ============

@app.post("/api/register", response_model=Token)
def register(data: UserRegister, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(400, "Email уже зарегистрирован")
    colors = ["#2563eb","#16a34a","#d97706","#7c3aed","#db2777","#059669","#ea580c","#4f46e5"]
    user = User(
        name=data.name, email=data.email,
        password_hash=hash_password(data.password),
        department=data.department, position=data.position,
        color=colors[db.query(User).count() % len(colors)],
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_token(user.id)
    return Token(access_token=token, user=UserOut.model_validate(user))


@app.post("/api/login", response_model=Token)
def login(data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "Неверный email или пароль")
    token = create_token(user.id)
    return Token(access_token=token, user=UserOut.model_validate(user))


@app.get("/api/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return UserOut.model_validate(user)


# ============ USERS ============

@app.get("/api/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return [UserOut.model_validate(u) for u in db.query(User).all()]


@app.post("/api/users", response_model=UserOut)
def create_user(data: UserCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role != "admin":
        raise HTTPException(403, "Только админ может добавлять сотрудников")
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(400, "Email уже существует")
    colors = ["#2563eb","#16a34a","#d97706","#7c3aed","#db2777","#059669","#ea580c"]
    new_user = User(
        name=data.name, email=data.email,
        password_hash=hash_password(data.password),
        role=data.role, department=data.department, position=data.position,
        color=colors[db.query(User).count() % len(colors)],
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return UserOut.model_validate(new_user)


# ============ TAGS ============

@app.get("/api/tags", response_model=list[TagOut])
def list_tags(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return [TagOut.model_validate(t) for t in db.query(Tag).all()]


# ============ DOCUMENTS ============

TYPE_PREFIX = {"contract":"ДОГ","invoice":"СЧ","order":"ПР","report":"ОТЧ","memo":"СЗ","statement":"ЗАЯ","other":"ДОК"}

def gen_number(db: Session, doc_type: str) -> str:
    prefix = TYPE_PREFIX.get(doc_type, "ДОК")
    year = datetime.now().year
    count = db.query(Document).filter(Document.doc_type == doc_type).count() + 1
    total = db.query(Document).count() + 1
    return f"{prefix}-{year}-{str(count).zfill(3)} (№{total})"


def doc_to_out(doc: Document) -> DocumentOut:
    return DocumentOut(
        id=doc.id, number=doc.number or "", title=doc.title,
        description=doc.description or "", content=doc.content,
        doc_type=doc.doc_type, status=doc.status, priority=doc.priority or "normal",
        sequential=doc.sequential, deadline=doc.deadline or "",
        author_id=doc.author_id, author_name=doc.author_user.name if doc.author_user else "",
        created_at=doc.created_at, updated_at=doc.updated_at,
        approvals=[ApprovalOut(
            id=a.id, user_id=a.user_id, user_name=a.user.name if a.user else "",
            status=a.status, comment=a.comment or "", signature=a.signature or "",
            order_num=a.order_num, decided_at=a.decided_at
        ) for a in sorted(doc.approvals, key=lambda x: x.order_num)],
        comments=[CommentOut(
            id=c.id, user_id=c.user_id, user_name=c.user.name if c.user else "",
            text=c.text, created_at=c.created_at
        ) for c in doc.comments],
        history=[{"id": h.id, "user_name": h.user_name, "text": h.text, "created_at": h.created_at} for h in doc.history],
        versions=[{"id": v.id, "title": v.title, "content": v.content, "user_name": v.user_name, "created_at": v.created_at} for v in doc.versions],
        attachments=[{"id": att.id, "filename": att.filename, "size": att.size} for att in doc.attachments],
        tags=[TagOut.model_validate(t) for t in doc.tags],
        related_doc_ids=[r.id for r in doc.related_docs],
    )


def load_doc(db: Session, doc_id: int) -> Document:
    doc = db.query(Document).options(
        joinedload(Document.author_user),
        joinedload(Document.approvals).joinedload(Approval.user),
        joinedload(Document.comments).joinedload(Comment.user),
        joinedload(Document.history),
        joinedload(Document.versions),
        joinedload(Document.attachments),
        joinedload(Document.tags),
        joinedload(Document.related_docs),
    ).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(404, "Документ не найден")
    return doc


def add_history(db: Session, doc: Document, user_name: str, text: str):
    db.add(History(document_id=doc.id, user_name=user_name, text=text))


def add_notification(db: Session, user_id: int, notif_type: str, title: str, message: str, doc_id: int = None):
    db.add(Notification(user_id=user_id, notif_type=notif_type, title=title, message=message, doc_id=doc_id))


@app.get("/api/documents", response_model=list[DocumentOut])
def list_documents(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    docs = db.query(Document).options(
        joinedload(Document.author_user),
        joinedload(Document.approvals).joinedload(Approval.user),
        joinedload(Document.comments).joinedload(Comment.user),
        joinedload(Document.history),
        joinedload(Document.versions),
        joinedload(Document.attachments),
        joinedload(Document.tags),
        joinedload(Document.related_docs),
    ).order_by(Document.updated_at.desc()).all()
    return [doc_to_out(d) for d in docs]


@app.post("/api/documents", response_model=DocumentOut)
def create_document(data: DocumentCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    number = gen_number(db, data.doc_type)
    doc = Document(
        number=number, title=data.title, description=data.description,
        content=data.content, doc_type=data.doc_type, status=data.status,
        priority=data.priority, sequential=data.sequential,
        deadline=data.deadline, author_id=user.id,
    )
    db.add(doc)
    db.flush()

    # Tags
    if data.tag_ids:
        tags = db.query(Tag).filter(Tag.id.in_(data.tag_ids)).all()
        doc.tags = tags

    # Attachments
    for att in data.attachments:
        db.add(Attachment(document_id=doc.id, filename=att.get("name",""), size=att.get("size","")))

    # Related docs
    if data.related_doc_ids:
        related = db.query(Document).filter(Document.id.in_(data.related_doc_ids)).all()
        doc.related_docs = related

    add_history(db, doc, user.name, "Создан")

    # Approvers
    if data.status == "pending" and data.approver_ids:
        for i, uid in enumerate(data.approver_ids):
            db.add(Approval(document_id=doc.id, user_id=uid, order_num=i))
        add_history(db, doc, user.name, "Отправлен на согласование")
        for uid in data.approver_ids:
            add_notification(db, uid, "approval_request", "Документ на согласование", f'{user.name}: "{data.title}"', doc.id)

    db.commit()
    return doc_to_out(load_doc(db, doc.id))


@app.get("/api/documents/{doc_id}", response_model=DocumentOut)
def get_document(doc_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return doc_to_out(load_doc(db, doc_id))


@app.put("/api/documents/{doc_id}", response_model=DocumentOut)
def update_document(doc_id: int, data: DocumentCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    doc = load_doc(db, doc_id)
    if doc.author_id != user.id and user.role != "admin":
        raise HTTPException(403, "Нет прав")

    # Save version if content changed
    if doc.content != data.content or doc.title != data.title:
        db.add(Version(document_id=doc.id, title=doc.title, content=doc.content, user_name=user.name))

    doc.title = data.title
    doc.description = data.description
    doc.content = data.content
    doc.doc_type = data.doc_type
    doc.status = data.status
    doc.priority = data.priority
    doc.sequential = data.sequential
    doc.deadline = data.deadline
    doc.updated_at = datetime.now(timezone.utc)

    # Tags
    tags = db.query(Tag).filter(Tag.id.in_(data.tag_ids)).all() if data.tag_ids else []
    doc.tags = tags

    # Attachments — replace
    for att in doc.attachments:
        db.delete(att)
    for att in data.attachments:
        db.add(Attachment(document_id=doc.id, filename=att.get("name",""), size=att.get("size","")))

    # Related docs
    related = db.query(Document).filter(Document.id.in_(data.related_doc_ids)).all() if data.related_doc_ids else []
    doc.related_docs = related

    add_history(db, doc, user.name, "Отредактирован")

    # Approvers on pending
    if data.status == "pending" and data.approver_ids:
        for a in doc.approvals:
            db.delete(a)
        db.flush()
        for i, uid in enumerate(data.approver_ids):
            db.add(Approval(document_id=doc.id, user_id=uid, order_num=i))
        add_history(db, doc, user.name, "На согласование")
        for uid in data.approver_ids:
            add_notification(db, uid, "approval_request", "Документ на согласование", f'{user.name}: "{data.title}"', doc.id)

    db.commit()
    return doc_to_out(load_doc(db, doc.id))


@app.delete("/api/documents/{doc_id}")
def delete_document(doc_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    doc = load_doc(db, doc_id)
    if doc.author_id != user.id and user.role != "admin":
        raise HTTPException(403, "Нет прав")
    db.delete(doc)
    db.commit()
    return {"ok": True}


# ============ APPROVAL ACTIONS ============

@app.post("/api/documents/{doc_id}/approve", response_model=DocumentOut)
def approve_document(doc_id: int, data: ApprovalAction, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    doc = load_doc(db, doc_id)
    if doc.status != "pending":
        raise HTTPException(400, "Документ не на согласовании")

    approval = None
    for i, a in enumerate(sorted(doc.approvals, key=lambda x: x.order_num)):
        if a.user_id == user.id and a.status == "pending":
            if doc.sequential:
                # Check all previous are approved
                for prev in sorted(doc.approvals, key=lambda x: x.order_num):
                    if prev.order_num < a.order_num and prev.status != "approved":
                        raise HTTPException(400, "Дождитесь предыдущего согласующего")
            approval = a
            break

    if not approval:
        raise HTTPException(400, "Вы не можете согласовать этот документ")

    approval.status = "approved"
    approval.comment = data.comment
    approval.signature = secrets.token_hex(32)
    approval.decided_at = datetime.now(timezone.utc)

    add_history(db, doc, user.name, f"ЭЦП: {user.name}")

    # Check if all approved
    db.flush()
    all_approved = all(a.status == "approved" for a in doc.approvals)
    if all_approved:
        doc.status = "approved"
        add_history(db, doc, user.name, "Полностью согласован")
        add_notification(db, doc.author_id, "approved", "Согласован", f'"{doc.title}" согласован', doc.id)

    doc.updated_at = datetime.now(timezone.utc)
    db.commit()
    return doc_to_out(load_doc(db, doc.id))


@app.post("/api/documents/{doc_id}/reject", response_model=DocumentOut)
def reject_document(doc_id: int, data: ApprovalAction, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    doc = load_doc(db, doc_id)
    if doc.status != "pending":
        raise HTTPException(400, "Документ не на согласовании")

    approval = None
    for a in doc.approvals:
        if a.user_id == user.id and a.status == "pending":
            approval = a
            break

    if not approval:
        raise HTTPException(400, "Вы не можете отклонить этот документ")

    if not data.comment:
        raise HTTPException(400, "Укажите причину отклонения")

    approval.status = "rejected"
    approval.comment = data.comment
    approval.decided_at = datetime.now(timezone.utc)

    doc.status = "rejected"
    doc.updated_at = datetime.now(timezone.utc)

    add_history(db, doc, user.name, f"Отклонён: {user.name} — {data.comment}")
    add_notification(db, doc.author_id, "rejected", "Отклонён", f'{user.name} отклонил "{doc.title}"', doc.id)

    db.commit()
    return doc_to_out(load_doc(db, doc.id))


@app.post("/api/documents/{doc_id}/recall", response_model=DocumentOut)
def recall_document(doc_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    doc = load_doc(db, doc_id)
    if doc.status != "pending" or doc.author_id != user.id:
        raise HTTPException(400, "Нельзя отозвать")
    doc.status = "draft"
    for a in doc.approvals:
        a.status = "pending"
        a.comment = ""
        a.decided_at = None
        a.signature = ""
    doc.updated_at = datetime.now(timezone.utc)
    add_history(db, doc, user.name, "Отозван с согласования")
    db.commit()
    return doc_to_out(load_doc(db, doc.id))


@app.post("/api/documents/{doc_id}/resend", response_model=DocumentOut)
def resend_document(doc_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    doc = load_doc(db, doc_id)
    if doc.author_id != user.id:
        raise HTTPException(403, "Нет прав")
    doc.status = "pending"
    for a in doc.approvals:
        a.status = "pending"
        a.comment = ""
        a.decided_at = None
        a.signature = ""
    doc.updated_at = datetime.now(timezone.utc)
    add_history(db, doc, user.name, "Повторно на согласование")
    for a in doc.approvals:
        add_notification(db, a.user_id, "approval_request", "Повторно на согласование", f'{user.name}: "{doc.title}"', doc.id)
    db.commit()
    return doc_to_out(load_doc(db, doc.id))


@app.post("/api/documents/{doc_id}/archive", response_model=DocumentOut)
def archive_document(doc_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    doc = load_doc(db, doc_id)
    doc.status = "archived"
    doc.updated_at = datetime.now(timezone.utc)
    add_history(db, doc, user.name, "В архив")
    db.commit()
    return doc_to_out(load_doc(db, doc.id))


@app.post("/api/documents/{doc_id}/copy", response_model=DocumentOut)
def copy_document(doc_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    orig = load_doc(db, doc_id)
    number = gen_number(db, orig.doc_type)
    doc = Document(
        number=number, title=orig.title + " (копия)", description=orig.description,
        content=orig.content, doc_type=orig.doc_type, status="draft",
        priority=orig.priority, deadline="", author_id=user.id,
    )
    db.add(doc)
    db.flush()
    doc.tags = list(orig.tags)
    for att in orig.attachments:
        db.add(Attachment(document_id=doc.id, filename=att.filename, size=att.size))
    add_history(db, doc, user.name, f"Создан (копия из {orig.number})")
    db.commit()
    return doc_to_out(load_doc(db, doc.id))


@app.post("/api/documents/{doc_id}/delegate")
def delegate_approval(doc_id: int, to_user_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    doc = load_doc(db, doc_id)
    to_user = db.query(User).filter(User.id == to_user_id).first()
    if not to_user:
        raise HTTPException(404, "Пользователь не найден")
    approval = None
    for a in doc.approvals:
        if a.user_id == user.id and a.status == "pending":
            approval = a
            break
    if not approval:
        raise HTTPException(400, "Нет активного согласования")
    approval.user_id = to_user_id
    add_history(db, doc, user.name, f"Делегировано: {user.name} -> {to_user.name}")
    add_notification(db, to_user_id, "approval_request", "Делегировано", f'{user.name} делегировал "{doc.title}"', doc.id)
    doc.updated_at = datetime.now(timezone.utc)
    db.commit()
    return doc_to_out(load_doc(db, doc.id))


# ============ COMMENTS ============

@app.post("/api/documents/{doc_id}/comments", response_model=DocumentOut)
def add_comment(doc_id: int, data: CommentCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    doc = load_doc(db, doc_id)
    db.add(Comment(document_id=doc.id, user_id=user.id, text=data.text))
    add_history(db, doc, user.name, "Комментарий: " + data.text[:40])
    if doc.author_id != user.id:
        add_notification(db, doc.author_id, "comment", "Комментарий", f'{user.name}: "{doc.title}"', doc.id)
    doc.updated_at = datetime.now(timezone.utc)
    db.commit()
    return doc_to_out(load_doc(db, doc.id))


# ============ NOTIFICATIONS ============

@app.get("/api/notifications", response_model=list[NotificationOut])
def list_notifications(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    notifs = db.query(Notification).filter(Notification.user_id == user.id).order_by(Notification.created_at.desc()).all()
    return [NotificationOut.model_validate(n) for n in notifs]


@app.post("/api/notifications/read-all")
def read_all_notifications(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    db.query(Notification).filter(Notification.user_id == user.id, Notification.read == False).update({"read": True})
    db.commit()
    return {"ok": True}


@app.post("/api/notifications/{notif_id}/read")
def read_notification(notif_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    n = db.query(Notification).filter(Notification.id == notif_id, Notification.user_id == user.id).first()
    if n:
        n.read = True
        db.commit()
    return {"ok": True}


# ============ ROUTES ============

@app.get("/api/routes", response_model=list[RouteOut])
def list_routes(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return [RouteOut.model_validate(r) for r in db.query(ApprovalRoute).all()]


@app.post("/api/routes", response_model=RouteOut)
def create_route(data: RouteCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    route = ApprovalRoute(name=data.name, user_ids=",".join(str(x) for x in data.user_ids), sequential=data.sequential)
    db.add(route)
    db.commit()
    db.refresh(route)
    return RouteOut.model_validate(route)


@app.delete("/api/routes/{route_id}")
def delete_route(route_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    route = db.query(ApprovalRoute).filter(ApprovalRoute.id == route_id).first()
    if route:
        db.delete(route)
        db.commit()
    return {"ok": True}


# ============ STATIC ============

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def index():
    return FileResponse("static/index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)), reload=True)
