import os
from datetime import datetime, timezone
from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, joinedload
from database import engine, get_db, Base
from models import (
    User, Document, Tag, Approval, Comment, Notification,
    History, Version, Attachment, ApprovalRoute, doc_tags, doc_related, Task,
)
from schemas import (
    UserRegister, UserLogin, UserOut, Token, UserCreate, DeputySet,
    DocumentCreate, DocumentOut, ApprovalOut, CommentOut, CommentCreate,
    ApprovalAction, NotificationOut, RouteCreate, RouteOut, TagOut,
    TaskCreate, TaskUpdate, TaskOut,
)
from auth import hash_password, verify_password, create_token, get_current_user
import secrets
import shutil
import json

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = FastAPI(title="ЭДО API")


# --- Startup ---
def run_migrations(eng):
    """Add missing columns/tables to existing DB without dropping data."""
    from sqlalchemy import text, inspect
    insp = inspect(eng)
    existing_tables = insp.get_table_names()
    with eng.connect() as conn:
        migrations = [
            ("documents", "extra_fields", "TEXT DEFAULT '{}'"),
            ("documents", "deleted", "BOOLEAN DEFAULT FALSE"),
            ("users", "deputy_id", "INTEGER"),
            ("users", "login", "VARCHAR(20)"),
            ("attachments", "filepath", "VARCHAR(1000) DEFAULT ''"),
            ("attachments", "filesize", "INTEGER DEFAULT 0"),
        ]
        for table, col, col_type in migrations:
            if table in existing_tables:
                cols = [c["name"] for c in insp.get_columns(table)]
                if col not in cols:
                    conn.execute(text(f'ALTER TABLE {table} ADD COLUMN {col} {col_type}'))
        conn.commit()



@app.on_event("startup")
def startup():
    run_migrations(engine)
    Base.metadata.create_all(bind=engine)
    db = next(get_db())
    if db.query(Tag).count() == 0:
        for name, color in [("Срочно","red"),("Финансы","green"),("Кадры","blue"),("Продажи","yellow"),("Важно","purple"),("Личное","pink")]:
            db.add(Tag(name=name, color=color))
        db.commit()

    # Seed 3 demo users
    demo_users = [
        {"login": "admedo", "name": "Администратор", "email": "admin@edo.com", "password": "admin123",
         "role": "admin", "department": "Руководство", "position": "Системный администратор", "color": "#2563eb"},
        {"login": "manger", "name": "Менеджер Иванов", "email": "manager@edo.com", "password": "manager123",
         "role": "user", "department": "Управление", "position": "Менеджер проектов", "color": "#16a34a"},
        {"login": "usredo", "name": "Сотрудник Петров", "email": "user@edo.com", "password": "user123",
         "role": "user", "department": "Отдел разработки", "position": "Специалист", "color": "#7c3aed"},
        {"login": "buhgal", "name": "Бухгалтер Смирнова", "email": "buh@edo.com", "password": "buh123",
         "role": "user", "department": "Бухгалтерия", "position": "Главный бухгалтер", "color": "#ea580c"},
    ]
    for u in demo_users:
        existing = db.query(User).filter(User.email == u["email"]).first()
        if not existing:
            db.add(User(
                login=u["login"], name=u["name"], email=u["email"],
                password_hash=hash_password(u["password"]),
                role=u["role"], department=u["department"],
                position=u["position"], color=u["color"],
            ))
        else:
            existing.login = u["login"]
            existing.name = u["name"]
            existing.role = u["role"]
            existing.department = u["department"]
            existing.position = u["position"]
            existing.color = u["color"]
            existing.password_hash = hash_password(u["password"])
    db.commit()

    # Удалить старых тестовых пользователей без логина
    old_users = db.query(User).filter(User.login == None).all()
    for ou in old_users:
        try:
            db.delete(ou)
            db.commit()
        except Exception:
            db.rollback()
    db.close()


# ============ AUTH ============

@app.post("/api/register", response_model=Token)
def register(data: UserRegister, db: Session = Depends(get_db)):
    login_val = data.login.strip().lower()
    if not login_val.isalpha() or len(login_val) != 6:
        raise HTTPException(400, "Логин должен состоять из 6 английских букв")
    if db.query(User).filter(User.login == login_val).first():
        raise HTTPException(400, "Логин уже занят")
    colors = ["#2563eb","#16a34a","#d97706","#7c3aed","#db2777","#059669","#ea580c","#4f46e5"]
    user = User(
        login=login_val, name=data.name, email=f"{login_val}@edo.local",
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
    login_val = data.login.strip().lower()
    user = db.query(User).filter(User.login == login_val).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "Неверный логин или пароль")
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
    login_val = data.login.strip().lower()
    if not login_val.isalpha() or len(login_val) != 6:
        raise HTTPException(400, "Логин должен состоять из 6 английских букв")
    if db.query(User).filter(User.login == login_val).first():
        raise HTTPException(400, "Логин уже занят")
    colors = ["#2563eb","#16a34a","#d97706","#7c3aed","#db2777","#059669","#ea580c"]
    new_user = User(
        login=login_val, name=data.name, email=f"{login_val}@edo.local",
        password_hash=hash_password(data.password),
        role=data.role, department=data.department, position=data.position,
        color=colors[db.query(User).count() % len(colors)],
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return UserOut.model_validate(new_user)


@app.put("/api/users/{user_id}/deputy", response_model=UserOut)
def set_deputy(user_id: int, data: DeputySet, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.id != user_id and user.role != "admin":
        raise HTTPException(403, "Нет прав")
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(404, "Пользователь не найден")
    if data.deputy_id:
        dep = db.query(User).filter(User.id == data.deputy_id).first()
        if not dep:
            raise HTTPException(404, "Заместитель не найден")
        if data.deputy_id == user_id:
            raise HTTPException(400, "Нельзя назначить себя заместителем")
    target.deputy_id = data.deputy_id
    db.commit()
    db.refresh(target)
    return UserOut.model_validate(target)


# ============ TAGS ============

@app.get("/api/tags", response_model=list[TagOut])
def list_tags(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return [TagOut.model_validate(t) for t in db.query(Tag).all()]


# ============ DOCUMENTS ============

TYPE_PREFIX = {
    "contract":"ДОГ","invoice":"СЧ","order":"ПР","report":"ОТЧ","memo":"СЗ",
    "statement":"ЗАЯ","protocol":"ПРОТ","letter":"ПИС","nda":"НДА",
    "vacation":"ОТП","trip":"КОМ","purchase":"ЗЗ","job_desc":"ДИ",
    "act":"АКТ","regulation":"ПОЛ",
    "advance_report":"АО","payment_order":"ПП","invoice_tax":"СФ",
    "waybill":"ТН","accounting_memo":"БС","power_of_attorney":"ДОВ",
    "cash_order":"КО","other":"ДОК",
}

def gen_number(db: Session, doc_type: str) -> str:
    prefix = TYPE_PREFIX.get(doc_type, "ДОК")
    year = datetime.now().year
    count = db.query(Document).filter(Document.doc_type == doc_type).count() + 1
    total = db.query(Document).count() + 1
    return f"{prefix}-{year}-{str(count).zfill(3)} (№{total})"


def doc_to_out(doc: Document) -> DocumentOut:
    return DocumentOut(
        id=doc.id, number=doc.number or "", title=doc.title,
        description=doc.description or "", content=doc.content or "",
        doc_type=doc.doc_type, status=doc.status, priority=doc.priority or "normal",
        sequential=doc.sequential, deadline=doc.deadline or "",
        extra_fields=json.loads(doc.extra_fields) if isinstance(doc.extra_fields, str) else (doc.extra_fields or {}),
        deleted=doc.deleted or False,
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
        attachments=[{"id": att.id, "filename": att.filename, "filepath": att.filepath or "", "size": att.size, "filesize": att.filesize or 0} for att in doc.attachments],
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
def list_documents(include_deleted: bool = False, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = db.query(Document).options(
        joinedload(Document.author_user),
        joinedload(Document.approvals).joinedload(Approval.user),
        joinedload(Document.comments).joinedload(Comment.user),
        joinedload(Document.history),
        joinedload(Document.versions),
        joinedload(Document.attachments),
        joinedload(Document.tags),
        joinedload(Document.related_docs),
    )
    if not include_deleted:
        q = q.filter(Document.deleted == False)
    docs = q.order_by(Document.updated_at.desc()).all()
    return [doc_to_out(d) for d in docs]


@app.get("/api/documents/trash", response_model=list[DocumentOut])
def list_trash(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    docs = db.query(Document).options(
        joinedload(Document.author_user),
        joinedload(Document.approvals).joinedload(Approval.user),
        joinedload(Document.comments).joinedload(Comment.user),
        joinedload(Document.history),
        joinedload(Document.versions),
        joinedload(Document.attachments),
        joinedload(Document.tags),
        joinedload(Document.related_docs),
    ).filter(Document.deleted == True).order_by(Document.updated_at.desc()).all()
    return [doc_to_out(d) for d in docs]


@app.post("/api/documents", response_model=DocumentOut)
def create_document(data: DocumentCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    number = gen_number(db, data.doc_type)
    doc = Document(
        number=number, title=data.title, description=data.description,
        content=data.content, doc_type=data.doc_type, status=data.status,
        priority=data.priority, sequential=data.sequential,
        deadline=data.deadline, extra_fields=json.dumps(data.extra_fields or {}, ensure_ascii=False),
        author_id=user.id,
    )
    db.add(doc)
    db.flush()

    if data.tag_ids:
        tags = db.query(Tag).filter(Tag.id.in_(data.tag_ids)).all()
        doc.tags = tags

    for att in data.attachments:
        db.add(Attachment(document_id=doc.id, filename=att.get("name",""), size=att.get("size","")))

    if data.related_doc_ids:
        related = db.query(Document).filter(Document.id.in_(data.related_doc_ids)).all()
        doc.related_docs = related

    add_history(db, doc, user.name, "Создан")

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
    doc.extra_fields = json.dumps(data.extra_fields or {}, ensure_ascii=False)
    doc.updated_at = datetime.now(timezone.utc)

    tags = db.query(Tag).filter(Tag.id.in_(data.tag_ids)).all() if data.tag_ids else []
    doc.tags = tags

    for att in doc.attachments:
        db.delete(att)
    for att in data.attachments:
        db.add(Attachment(document_id=doc.id, filename=att.get("name",""), size=att.get("size","")))

    related = db.query(Document).filter(Document.id.in_(data.related_doc_ids)).all() if data.related_doc_ids else []
    doc.related_docs = related

    add_history(db, doc, user.name, "Отредактирован")

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


# Мягкое удаление (в корзину)
@app.delete("/api/documents/{doc_id}")
def delete_document(doc_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    doc = load_doc(db, doc_id)
    if doc.author_id != user.id and user.role != "admin":
        raise HTTPException(403, "Нет прав")
    doc.deleted = True
    doc.updated_at = datetime.now(timezone.utc)
    add_history(db, doc, user.name, "Перемещён в корзину")
    db.commit()
    return {"ok": True}


# Восстановить из корзины
@app.post("/api/documents/{doc_id}/restore")
def restore_document(doc_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    doc = load_doc(db, doc_id)
    if doc.author_id != user.id and user.role != "admin":
        raise HTTPException(403, "Нет прав")
    doc.deleted = False
    doc.updated_at = datetime.now(timezone.utc)
    add_history(db, doc, user.name, "Восстановлен из корзины")
    db.commit()
    return {"ok": True}


# Окончательное удаление
@app.delete("/api/documents/{doc_id}/permanent")
def permanent_delete(doc_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    doc = load_doc(db, doc_id)
    if doc.author_id != user.id and user.role != "admin":
        raise HTTPException(403, "Нет прав")
    # Delete uploaded files
    for att in doc.attachments:
        if att.filepath and os.path.exists(att.filepath):
            os.remove(att.filepath)
    db.delete(doc)
    db.commit()
    return {"ok": True}


# ============ APPROVAL ACTIONS ============

def find_approval_for_user(doc, user, db):
    """Find pending approval for user (direct or as deputy)."""
    sorted_approvals = sorted(doc.approvals, key=lambda x: x.order_num)
    # Direct match
    for a in sorted_approvals:
        if a.user_id == user.id and a.status == "pending":
            if doc.sequential:
                for prev in sorted_approvals:
                    if prev.order_num < a.order_num and prev.status != "approved":
                        return None, "Дождитесь предыдущего согласующего"
            return a, None
    # Deputy match
    for a in sorted_approvals:
        if a.status == "pending":
            approver = db.query(User).filter(User.id == a.user_id).first()
            if approver and approver.deputy_id == user.id:
                if doc.sequential:
                    for prev in sorted_approvals:
                        if prev.order_num < a.order_num and prev.status != "approved":
                            return None, "Дождитесь предыдущего согласующего"
                return a, None
    return None, None


@app.post("/api/documents/{doc_id}/approve", response_model=DocumentOut)
def approve_document(doc_id: int, data: ApprovalAction, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    doc = load_doc(db, doc_id)
    if doc.status != "pending":
        raise HTTPException(400, "Документ не на согласовании")

    approval, err = find_approval_for_user(doc, user, db)
    if err:
        raise HTTPException(400, err)
    if not approval:
        raise HTTPException(400, "Вы не можете согласовать этот документ")

    is_deputy = approval.user_id != user.id
    approval.status = "approved"
    approval.comment = data.comment
    approval.signature = secrets.token_hex(32)
    approval.decided_at = datetime.now(timezone.utc)

    if is_deputy:
        approver = db.query(User).filter(User.id == approval.user_id).first()
        add_history(db, doc, user.name, f"ЭЦП (заместитель {approver.name}): {user.name}")
    else:
        add_history(db, doc, user.name, f"ЭЦП: {user.name}")

    db.flush()

    # Notify next approver in sequential mode
    if doc.sequential:
        sorted_approvals = sorted(doc.approvals, key=lambda x: x.order_num)
        for next_a in sorted_approvals:
            if next_a.status == "pending":
                add_notification(db, next_a.user_id, "approval_request", "Ваша очередь", f'Согласуйте "{doc.title}"', doc.id)
                break

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

    approval, err = find_approval_for_user(doc, user, db)
    if err:
        raise HTTPException(400, err)
    if not approval:
        raise HTTPException(400, "Вы не можете отклонить этот документ")

    if not data.comment:
        raise HTTPException(400, "Укажите причину отклонения")

    is_deputy = approval.user_id != user.id
    approval.status = "rejected"
    approval.comment = data.comment
    approval.decided_at = datetime.now(timezone.utc)

    doc.status = "rejected"
    doc.updated_at = datetime.now(timezone.utc)

    if is_deputy:
        approver = db.query(User).filter(User.id == approval.user_id).first()
        add_history(db, doc, user.name, f"Отклонён (заместитель {approver.name}): {user.name} — {data.comment}")
    else:
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
        priority=orig.priority, deadline="", extra_fields=orig.extra_fields or "{}",
        author_id=user.id,
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
    approval, _ = find_approval_for_user(doc, user, db)
    if not approval:
        raise HTTPException(400, "Нет активного согласования")
    approval.user_id = to_user_id
    add_history(db, doc, user.name, f"Делегировано: {user.name} -> {to_user.name}")
    add_notification(db, to_user_id, "approval_request", "Делегировано", f'{user.name} делегировал "{doc.title}"', doc.id)
    doc.updated_at = datetime.now(timezone.utc)
    db.commit()
    return doc_to_out(load_doc(db, doc.id))


# ============ FILE UPLOAD ============

@app.post("/api/documents/{doc_id}/upload")
async def upload_file(doc_id: int, file: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    doc = load_doc(db, doc_id)
    doc_dir = os.path.join(UPLOAD_DIR, str(doc_id))
    os.makedirs(doc_dir, exist_ok=True)
    safe_name = secrets.token_hex(8) + "_" + (file.filename or "file")
    filepath = os.path.join(doc_dir, safe_name)
    with open(filepath, "wb") as f:
        content = await file.read()
        f.write(content)
    att = Attachment(
        document_id=doc_id, filename=file.filename or "file",
        filepath=filepath, size=str(len(content)),
        filesize=len(content),
    )
    db.add(att)
    add_history(db, doc, user.name, f"Файл загружен: {file.filename}")
    doc.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(att)
    return {"id": att.id, "filename": att.filename, "size": att.size, "filesize": att.filesize}


@app.get("/api/attachments/{att_id}/download")
def download_file(att_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    att = db.query(Attachment).filter(Attachment.id == att_id).first()
    if not att or not att.filepath or not os.path.exists(att.filepath):
        raise HTTPException(404, "Файл не найден")
    return FileResponse(att.filepath, filename=att.filename)


@app.delete("/api/attachments/{att_id}")
def delete_file(att_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    att = db.query(Attachment).filter(Attachment.id == att_id).first()
    if not att:
        raise HTTPException(404, "Файл не найден")
    if att.filepath and os.path.exists(att.filepath):
        os.remove(att.filepath)
    db.delete(att)
    db.commit()
    return {"ok": True}


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


# ============ TASKS (Поручения) ============

@app.get("/api/tasks", response_model=list[TaskOut])
def list_tasks(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    tasks = db.query(Task).filter(
        (Task.author_id == user.id) | (Task.assignee_id == user.id)
    ).order_by(Task.created_at.desc()).all()
    result = []
    for t in tasks:
        out = TaskOut.model_validate(t)
        out.author_name = t.author.name if t.author else ""
        out.assignee_name = t.assignee.name if t.assignee else ""
        result.append(out)
    return result


@app.post("/api/tasks", response_model=TaskOut)
def create_task(data: TaskCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    assignee = db.query(User).filter(User.id == data.assignee_id).first()
    if not assignee:
        raise HTTPException(404, "Исполнитель не найден")
    task = Task(
        title=data.title, description=data.description,
        document_id=data.document_id, author_id=user.id,
        assignee_id=data.assignee_id, priority=data.priority,
        deadline=data.deadline,
    )
    db.add(task)
    db.flush()
    add_notification(db, data.assignee_id, "task", "Новое поручение",
                     f'{user.name}: "{data.title}"', data.document_id)
    db.commit()
    db.refresh(task)
    out = TaskOut.model_validate(task)
    out.author_name = user.name
    out.assignee_name = assignee.name
    return out


@app.put("/api/tasks/{task_id}", response_model=TaskOut)
def update_task(task_id: int, data: TaskUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(404, "Поручение не найдено")
    if task.author_id != user.id and task.assignee_id != user.id and user.role != "admin":
        raise HTTPException(403, "Нет прав")
    if data.title is not None:
        task.title = data.title
    if data.description is not None:
        task.description = data.description
    if data.status is not None:
        old_status = task.status
        task.status = data.status
        if data.status == "completed" and old_status != "completed":
            add_notification(db, task.author_id, "task_done", "Поручение выполнено",
                             f'"{task.title}" выполнено', task.document_id)
    if data.priority is not None:
        task.priority = data.priority
    if data.deadline is not None:
        task.deadline = data.deadline
    task.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(task)
    out = TaskOut.model_validate(task)
    out.author_name = task.author.name if task.author else ""
    out.assignee_name = task.assignee.name if task.assignee else ""
    return out


@app.delete("/api/tasks/{task_id}")
def delete_task(task_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(404, "Поручение не найдено")
    if task.author_id != user.id and user.role != "admin":
        raise HTTPException(403, "Нет прав")
    db.delete(task)
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

# ============ EXPORT (PDF / DOCX) ============

DOC_TYPE_LABELS = {
    "contract":"Договор","invoice":"Счёт на оплату","order":"Приказ","report":"Отчёт",
    "memo":"Служебная записка","statement":"Заявление","protocol":"Протокол","letter":"Письмо",
    "vacation":"Заявление на отпуск","trip":"Командировка","purchase":"Заявка на закупку",
    "job_desc":"Должностная инструкция","act":"Акт выполненных работ","regulation":"Положение",
    "nda":"NDA","advance_report":"Авансовый отчёт","payment_order":"Платёжное поручение",
    "invoice_tax":"Счёт-фактура","waybill":"Товарная накладная",
    "accounting_memo":"Бухгалтерская справка","power_of_attorney":"Доверенность",
    "cash_order":"Кассовый ордер","other":"Прочее",
}
STATUS_LABELS = {"draft":"Черновик","pending":"На согласовании","approved":"Согласован","rejected":"Отклонён","archived":"Архив"}
PRIORITY_LABELS = {"low":"Низкий","normal":"Обычный","high":"Высокий","urgent":"Срочный"}


@app.get("/api/documents/{doc_id}/export/docx")
def export_docx(doc_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from docx import Document as DocxDocument
    from docx.shared import Pt, RGBColor, Cm
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    import tempfile

    doc = load_doc(db, doc_id)
    d = doc_to_out(doc)

    dx = DocxDocument()
    style = dx.styles['Normal']
    style.font.name = 'Times New Roman'
    style.font.size = Pt(12)

    # Header
    h = dx.add_heading('', level=1)
    run = h.add_run(d.title)
    run.font.size = Pt(16)
    run.font.color.rgb = RGBColor(0, 0, 0)
    h.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Meta info
    dx.add_paragraph('')
    meta = [
        ('Номер', d.number), ('Тип', DOC_TYPE_LABELS.get(d.doc_type, d.doc_type)),
        ('Статус', STATUS_LABELS.get(d.status, d.status)),
        ('Приоритет', PRIORITY_LABELS.get(d.priority, d.priority)),
        ('Автор', d.author_name), ('Дедлайн', d.deadline or '—'),
        ('Создан', d.created_at.strftime('%d.%m.%Y %H:%M') if d.created_at else ''),
    ]
    for label, value in meta:
        p = dx.add_paragraph()
        p.add_run(f'{label}: ').bold = True
        p.add_run(str(value))

    if d.description:
        dx.add_paragraph('')
        p = dx.add_paragraph()
        p.add_run('Описание: ').bold = True
        p.add_run(d.description)

    # Extra fields
    if d.extra_fields:
        dx.add_paragraph('')
        p = dx.add_paragraph()
        p.add_run('Дополнительные поля:').bold = True
        for k, v in d.extra_fields.items():
            if v:
                p = dx.add_paragraph()
                p.add_run(f'  {k}: ').bold = True
                p.add_run(str(v))

    # Content
    dx.add_paragraph('')
    h2 = dx.add_heading('', level=2)
    h2.add_run('Содержание').font.size = Pt(14)
    for line in (d.content or '').split('\n'):
        dx.add_paragraph(line)

    # Approvals
    if d.approvals:
        dx.add_paragraph('')
        h3 = dx.add_heading('', level=2)
        h3.add_run('Согласование').font.size = Pt(14)
        for a in d.approvals:
            status_text = STATUS_LABELS.get(a.status, a.status)
            p = dx.add_paragraph()
            p.add_run(f'{a.user_name}: ').bold = True
            p.add_run(f'{status_text}')
            if a.comment:
                p.add_run(f' — {a.comment}')
            if a.decided_at:
                p.add_run(f' ({a.decided_at.strftime("%d.%m.%Y %H:%M")})')

    # Comments
    if d.comments:
        dx.add_paragraph('')
        h3 = dx.add_heading('', level=2)
        h3.add_run('Комментарии').font.size = Pt(14)
        for c in d.comments:
            p = dx.add_paragraph()
            p.add_run(f'{c.user_name}: ').bold = True
            p.add_run(c.text)

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.docx')
    dx.save(tmp.name)
    tmp.close()
    safe_title = "".join(c for c in d.title[:40] if c.isalnum() or c in ' _-').strip() or 'document'
    return FileResponse(tmp.name, filename=f'{d.number} {safe_title}.docx',
                        media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')


@app.get("/api/documents/{doc_id}/export/pdf")
def export_pdf(doc_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from fpdf import FPDF
    from fastapi.responses import JSONResponse
    import tempfile, traceback

    def clean(text):
        if not text:
            return ""
        out = []
        for ch in str(text):
            cp = ord(ch)
            if 0xD800 <= cp <= 0xDFFF:
                continue
            elif cp == 0xA0:
                out.append(' ')
            elif cp < 0x20 and cp not in (0x0A, 0x0D, 0x09):
                continue
            else:
                out.append(ch)
        return ''.join(out)

    doc = load_doc(db, doc_id)
    d = doc_to_out(doc)

    try:
        # Pre-clean all string fields
        d.title = clean(d.title)
        d.number = clean(d.number)
        d.description = clean(d.description)
        d.content = clean(d.content)
        d.author_name = clean(d.author_name)
        d.deadline = clean(d.deadline)
        for a in d.approvals:
            a.user_name = clean(a.user_name)
            a.comment = clean(a.comment)
        for c in d.comments:
            c.user_name = clean(c.user_name)
            c.text = clean(c.text)
        if d.extra_fields:
            d.extra_fields = {clean(str(k)): clean(str(v)) for k, v in d.extra_fields.items()}

        # Find DejaVu font
        font_path = font_bold_path = None
        for sp in ["/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/dejavu", "/usr/share/fonts/TTF"]:
            fp = os.path.join(sp, "DejaVuSans.ttf")
            fb = os.path.join(sp, "DejaVuSans-Bold.ttf")
            if os.path.exists(fp):
                font_path, font_bold_path = fp, fb
                break
        if not font_path:
            font_dir = os.path.join(os.path.dirname(__file__), "fonts")
            os.makedirs(font_dir, exist_ok=True)
            fp = os.path.join(font_dir, "DejaVuSans.ttf")
            fb = os.path.join(font_dir, "DejaVuSans-Bold.ttf")
            if not os.path.exists(fp):
                try:
                    import urllib.request
                    base = "https://raw.githubusercontent.com/dejavu-fonts/dejavu-fonts/master/ttf/"
                    urllib.request.urlretrieve(base + "DejaVuSans.ttf", fp)
                    urllib.request.urlretrieve(base + "DejaVuSans-Bold.ttf", fb)
                except Exception:
                    pass
            if os.path.exists(fp):
                font_path, font_bold_path = fp, fb

        pdf = FPDF()
        pdf.add_page()
        if font_path and os.path.exists(font_path):
            pdf.add_font('DejaVu', '', font_path)
            pdf.add_font('DejaVu', 'B', font_bold_path if font_bold_path and os.path.exists(font_bold_path) else font_path)
            font_name = 'DejaVu'
        else:
            font_name = 'Helvetica'
        pdf.set_auto_page_break(auto=True, margin=15)

        # Title
        pdf.set_font(font_name, 'B', 16)
        pdf.multi_cell(0, 10, d.title, align='C')
        pdf.ln(5)

        # Meta
        def add_field(label, value):
            pdf.set_font(font_name, 'B', 10)
            pdf.cell(40, 7, f'{label}:', ln=0)
            pdf.set_font(font_name, '', 10)
            pdf.cell(0, 7, clean(str(value)), ln=1)

        add_field('Номер', d.number)
        add_field('Тип', DOC_TYPE_LABELS.get(d.doc_type, d.doc_type))
        add_field('Статус', STATUS_LABELS.get(d.status, d.status))
        add_field('Приоритет', PRIORITY_LABELS.get(d.priority, d.priority))
        add_field('Автор', d.author_name)
        add_field('Дедлайн', d.deadline or '—')
        add_field('Создан', d.created_at.strftime('%d.%m.%Y %H:%M') if d.created_at else '')

        if d.description:
            pdf.ln(3)
            add_field('Описание', d.description)

        # Extra fields
        if d.extra_fields:
            pdf.ln(5)
            pdf.set_font(font_name, 'B', 12)
            pdf.cell(0, 8, 'Дополнительные поля', ln=1)
            for k, v in d.extra_fields.items():
                if v:
                    add_field(k, v)

        # Content
        pdf.ln(5)
        pdf.set_font(font_name, 'B', 12)
        pdf.cell(0, 8, 'Содержание', ln=1)
        pdf.set_font(font_name, '', 10)
        pdf.multi_cell(0, 6, d.content or '')

        # Approvals
        if d.approvals:
            pdf.ln(5)
            pdf.set_font(font_name, 'B', 12)
            pdf.cell(0, 8, 'Согласование', ln=1)
            for a in d.approvals:
                pdf.set_font(font_name, 'B', 10)
                pdf.cell(50, 7, a.user_name + ':', ln=0)
                pdf.set_font(font_name, '', 10)
                line = STATUS_LABELS.get(a.status, a.status)
                if a.comment:
                    line += f' — {a.comment}'
                pdf.cell(0, 7, line, ln=1)

        # Comments
        if d.comments:
            pdf.ln(5)
            pdf.set_font(font_name, 'B', 12)
            pdf.cell(0, 8, 'Комментарии', ln=1)
            for c in d.comments:
                pdf.set_font(font_name, 'B', 10)
                pdf.cell(50, 7, c.user_name + ':', ln=0)
                pdf.set_font(font_name, '', 10)
                pdf.multi_cell(0, 7, c.text)

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        pdf.output(tmp.name)
        tmp.close()
        safe_title = "".join(ch for ch in d.title[:40] if ch.isalnum() or ch in ' _-').strip() or 'document'
        return FileResponse(tmp.name, filename=f'{d.number} {safe_title}.pdf', media_type='application/pdf')
    except Exception:
        return JSONResponse(status_code=500, content={"detail": f"PDF error: {traceback.format_exc()[-2000:]}"})


app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def index():
    return FileResponse("static/index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)), reload=True)
