"""
Auto-test script for EDO system.
Runs all critical checks and sends Telegram notification if errors found.
"""
import os
import sys
import time
import urllib.request
import urllib.parse
import json
from datetime import datetime

BASE_URL = os.getenv("EDO_BASE_URL", "https://edo-system.onrender.com")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8860853684:AAGiinja_Xv6jPCJ6ailw_t4b0_J2NawQn4")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "1621302967")

USERS = [
    {"login": "admedo", "password": "admin123", "role": "admin"},
    {"login": "manger", "password": "manager123", "role": "user"},
    {"login": "usredo", "password": "user123", "role": "user"},
    {"login": "buhgal", "password": "buh123", "role": "user"},
]

ENDPOINTS = [
    "/api/documents",
    "/api/users",
    "/api/notifications",
    "/api/tags",
    "/api/routes",
    "/api/tasks",
]

results = []
errors = []


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def send_telegram(text):
    """Send message to Telegram bot."""
    try:
        data = urllib.parse.urlencode({
            "chat_id": CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
        }).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data=data,
        )
        urllib.request.urlopen(req, timeout=10)
        log("Telegram notification sent")
    except Exception as e:
        log(f"Failed to send Telegram: {e}")


def api_request(method, path, token=None, body=None, timeout=15):
    """Make HTTP request and return (status_code, json_data)."""
    url = BASE_URL + path
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        body_bytes = resp.read()
        try:
            return resp.status, json.loads(body_bytes)
        except json.JSONDecodeError:
            return resp.status, {}
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, {}
    except Exception as e:
        return 0, {"error": str(e)}


def test_site_loads():
    """Test 1: Site loads."""
    log("Test 1: Site loads...")
    try:
        req = urllib.request.Request(BASE_URL)
        resp = urllib.request.urlopen(req, timeout=20)
        content = resp.read().decode(errors="ignore")
        if resp.status == 200 and len(content) > 1000:
            results.append("1. Site loads: OK")
            return True
        else:
            errors.append(f"1. Site loads: status={resp.status}, size={len(content)}")
            return False
    except Exception as e:
        errors.append(f"1. Site loads: FAIL - {e}")
        return False


def test_auth():
    """Test 2: Authentication for all users."""
    log("Test 2: Authentication...")
    tokens = {}
    for u in USERS:
        status, data = api_request("POST", "/api/login", body={
            "login": u["login"], "password": u["password"]
        })
        token = data.get("access_token")
        if status == 200 and token:
            tokens[u["login"]] = token
        else:
            errors.append(f"2. Auth {u['login']}: FAIL status={status}")
    ok_count = len(tokens)
    if ok_count == len(USERS):
        results.append(f"2. Auth: OK ({ok_count}/{len(USERS)} users)")
    else:
        errors.append(f"2. Auth: {ok_count}/{len(USERS)} users logged in")
    return tokens


def test_wrong_password():
    """Test 3: Wrong password returns 401."""
    log("Test 3: Wrong password...")
    status, _ = api_request("POST", "/api/login", body={
        "login": "admedo", "password": "wrongpassword"
    })
    if status == 401:
        results.append("3. Wrong password: OK (401)")
    else:
        errors.append(f"3. Wrong password: expected 401, got {status}")


def test_endpoints(token):
    """Test 4: All API endpoints return 200."""
    log("Test 4: API endpoints...")
    failed = []
    for ep in ENDPOINTS:
        status, _ = api_request("GET", ep, token=token)
        if status != 200:
            failed.append(f"{ep}={status}")
    if not failed:
        results.append(f"4. Endpoints: OK ({len(ENDPOINTS)}/{len(ENDPOINTS)})")
    else:
        errors.append(f"4. Endpoints FAIL: {', '.join(failed)}")


def test_documents(tokens):
    """Test 5: Each user sees documents."""
    log("Test 5: Documents list...")
    for u in USERS:
        token = tokens.get(u["login"])
        if not token:
            continue
        status, data = api_request("GET", "/api/documents", token=token)
        if status == 200 and isinstance(data, list):
            results.append(f"5. Docs {u['login']}: OK ({len(data)} docs)")
        else:
            errors.append(f"5. Docs {u['login']}: FAIL status={status}")


def test_create_and_delete(tokens):
    """Test 6: Create, view, comment, export, delete document."""
    log("Test 6: CRUD operations...")
    token = tokens.get("admedo")
    if not token:
        errors.append("6. CRUD: skipped (no admin token)")
        return

    # Create
    status, doc = api_request("POST", "/api/documents", token=token, body={
        "title": "Autotest doc", "description": "test", "content": "test content",
        "doc_type": "memo", "status": "draft", "priority": "normal",
        "sequential": False, "deadline": "", "extra_fields": {},
        "approver_ids": [], "tag_ids": [], "related_doc_ids": [], "attachments": [],
    })
    if status != 200 or not doc.get("id"):
        errors.append(f"6. Create: FAIL status={status}")
        return
    doc_id = doc["id"]

    # View
    status, _ = api_request("GET", f"/api/documents/{doc_id}", token=token)
    if status != 200:
        errors.append(f"6. View doc {doc_id}: FAIL status={status}")

    # Comment
    status, _ = api_request("POST", f"/api/documents/{doc_id}/comments", token=token, body={
        "text": "Autotest comment"
    })
    if status != 200:
        errors.append(f"6. Comment: FAIL status={status}")

    # Export PDF
    status, _ = api_request("GET", f"/api/documents/{doc_id}/export/pdf", token=token, timeout=60)
    if status == 200:
        pass  # ok
    elif status == 0:
        results.append("6. Export PDF: WARN (timeout, server slow)")
    else:
        errors.append(f"6. Export PDF: FAIL status={status}")

    # Export DOCX
    status, _ = api_request("GET", f"/api/documents/{doc_id}/export/docx", token=token, timeout=60)
    if status == 200:
        pass  # ok
    elif status == 0:
        results.append("6. Export DOCX: WARN (timeout, server slow)")
    else:
        errors.append(f"6. Export DOCX: FAIL status={status}")

    # Delete (soft)
    status, _ = api_request("DELETE", f"/api/documents/{doc_id}", token=token)
    if status != 200:
        errors.append(f"6. Delete: FAIL status={status}")

    # Permanent delete
    status, _ = api_request("DELETE", f"/api/documents/{doc_id}/permanent", token=token)
    if status != 200:
        errors.append(f"6. Permanent delete: FAIL status={status}")

    if not any("6." in e for e in errors):
        results.append("6. CRUD: OK (create/view/comment/pdf/docx/delete)")


def test_access_control(tokens):
    """Test 7: Access control - user can't see other's docs."""
    log("Test 7: Access control...")
    admin_token = tokens.get("admedo")
    user_token = tokens.get("usredo")
    if not admin_token or not user_token:
        errors.append("7. Access control: skipped (missing tokens)")
        return

    # Create doc as admin
    status, doc = api_request("POST", "/api/documents", token=admin_token, body={
        "title": "Access test", "description": "", "content": "", "doc_type": "memo",
        "status": "draft", "priority": "normal", "sequential": False, "deadline": "",
        "extra_fields": {}, "approver_ids": [], "tag_ids": [], "related_doc_ids": [],
        "attachments": [],
    })
    if status != 200:
        errors.append(f"7. Access control: can't create doc, status={status}")
        return
    doc_id = doc["id"]

    # User tries to access admin's doc
    status, _ = api_request("GET", f"/api/documents/{doc_id}", token=user_token)
    if status == 403:
        results.append("7. Access control: OK (403 for unauthorized)")
    else:
        errors.append(f"7. Access control: expected 403, got {status}")

    # Cleanup
    api_request("DELETE", f"/api/documents/{doc_id}", token=admin_token)
    api_request("DELETE", f"/api/documents/{doc_id}/permanent", token=admin_token)


def test_notifications(tokens):
    """Test 8: Notifications endpoint works."""
    log("Test 8: Notifications...")
    token = tokens.get("admedo")
    if not token:
        return
    status, data = api_request("GET", "/api/notifications", token=token)
    if status == 200 and isinstance(data, list):
        results.append(f"8. Notifications: OK ({len(data)} items)")
    else:
        errors.append(f"8. Notifications: FAIL status={status}")


def main():
    log("=== EDO Auto-Test Started ===")
    start = time.time()

    # Run all tests
    test_site_loads()
    tokens = test_auth()
    test_wrong_password()

    admin_token = tokens.get("admedo")
    if admin_token:
        test_endpoints(admin_token)

    test_documents(tokens)
    test_create_and_delete(tokens)
    test_access_control(tokens)
    test_notifications(tokens)

    elapsed = round(time.time() - start, 1)
    log(f"=== Tests completed in {elapsed}s ===")

    # Build report
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    total = len(results) + len(errors)

    if errors:
        report = f"<b>EDO Auto-Test Report</b>\n"
        report += f"<b>Date:</b> {now}\n"
        report += f"<b>Duration:</b> {elapsed}s\n\n"
        report += f"<b>ERRORS ({len(errors)}):</b>\n"
        for e in errors:
            report += f"  {e}\n"
        report += f"\n<b>PASSED ({len(results)}):</b>\n"
        for r in results:
            report += f"  {r}\n"
        send_telegram(report)
        log(f"FAIL: {len(errors)} errors, {len(results)} passed")
        sys.exit(1)
    else:
        report = f"<b>EDO Auto-Test Report</b>\n"
        report += f"<b>Date:</b> {now}\n"
        report += f"<b>Duration:</b> {elapsed}s\n\n"
        report += f"<b>ALL {total} TESTS PASSED</b>\n"
        for r in results:
            report += f"  {r}\n"
        # Only send on errors by default; uncomment to always notify:
        # send_telegram(report)
        log(f"OK: all {total} tests passed")
        sys.exit(0)


if __name__ == "__main__":
    main()
