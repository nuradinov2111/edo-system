#!/usr/bin/env python3
"""Full system test for EDO."""
import urllib.request, urllib.parse, json, time

BASE = 'https://edo-system.onrender.com'
PASS = 0
FAIL = 0

def api(path, method='GET', data=None, headers=None, raw=False):
    h = headers or {}
    if data and not isinstance(data, bytes):
        body = json.dumps(data).encode()
        h['Content-Type'] = 'application/json'
    else:
        body = None
    req = urllib.request.Request(BASE + path, data=body, headers=h, method=method)
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        if raw:
            return {'status': resp.status, 'length': len(resp.read())}
        return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return {'error': e.code, 'detail': e.read().decode()[:500]}
    except Exception as e:
        return {'error': str(e)}

def test(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS [{PASS+FAIL:02d}] {name} {detail}")
    else:
        FAIL += 1
        print(f"  FAIL [{PASS+FAIL:02d}] {name} {detail}")

print("=" * 60)
print("FULL EDO SYSTEM TEST")
print("=" * 60)

# Login admin
r = api('/api/login', 'POST', {'login':'admedo','password':'admin123'})
test("Login admin", 'access_token' in r)
token = r.get('access_token', '')
admin_id = r.get('user', {}).get('id', 1)
AUTH = {'Authorization': f'Bearer {token}'}
time.sleep(0.5)

# Login user
r2 = api('/api/login', 'POST', {'login':'usredo','password':'user123'})
test("Login user", 'access_token' in r2)
user_token = r2.get('access_token', '')
user_id = r2.get('user', {}).get('id', 7)
UAUTH = {'Authorization': f'Bearer {user_token}'}
time.sleep(0.5)

# Documents
docs = api('/api/documents?limit=200', headers=AUTH)
test("List documents", isinstance(docs, list) and len(docs) > 0, f"count={len(docs) if isinstance(docs, list) else 0}")
time.sleep(0.5)

# Dashboard
dash = api('/api/dashboard', headers=AUTH)
test("Dashboard", isinstance(dash, dict) and 'total' in dash, f"total={dash.get('total', 0)}")
test("Dashboard overdue_tasks", 'overdue_tasks' in dash if isinstance(dash, dict) else False)
time.sleep(0.5)

# Create document
new_doc = api('/api/documents', 'POST', {
    'title': 'System test doc', 'doc_type': 'memo', 'content': 'Test content',
    'description': 'Auto test', 'status': 'draft', 'priority': 'normal'
}, headers=AUTH)
test("Create document", 'id' in new_doc, f"id={new_doc.get('id', '?')}")
test_doc_id = new_doc.get('id', 0)
time.sleep(0.5)

# QR Code
qr = api(f'/api/documents/{test_doc_id}/qr', headers=AUTH)
test("QR code", 'qr_base64' in qr, f"len={len(qr.get('qr_base64', ''))}")
time.sleep(0.5)

# Send to approval
upd = api(f'/api/documents/{test_doc_id}', 'PUT', {
    'title': 'System test doc', 'doc_type': 'memo', 'content': 'Test content',
    'status': 'pending', 'approver_ids': [admin_id]
}, headers=AUTH)
test("Send to approval", upd.get('status') == 'pending')
time.sleep(0.5)

# PDF export (draft/pending watermark)
pdf = api(f'/api/documents/{test_doc_id}/export/pdf', headers=AUTH, raw=True)
test("PDF export (watermark)", pdf.get('status') == 200, f"size={pdf.get('length', 0)}b")
time.sleep(0.5)

# Approve
apr = api(f'/api/documents/{test_doc_id}/approve', 'POST', {'comment': 'Test OK'}, headers=AUTH)
test("Approve document", apr.get('status') == 'approved')
time.sleep(0.5)

# PDF export (stamp)
pdf2 = api(f'/api/documents/{test_doc_id}/export/pdf', headers=AUTH, raw=True)
test("PDF export (stamp)", pdf2.get('status') == 200, f"size={pdf2.get('length', 0)}b")
time.sleep(0.5)

# DOCX export
docx = api(f'/api/documents/{test_doc_id}/export/docx', headers=AUTH, raw=True)
test("DOCX export", docx.get('status') == 200, f"size={docx.get('length', 0)}b")
time.sleep(0.5)

# Resolution
res = api(f'/api/documents/{test_doc_id}/resolution', 'POST', {'text': 'Execute ASAP'}, headers=AUTH)
test("Resolution", res.get('status') == 'resolved')
time.sleep(0.5)

# Comment
com = api(f'/api/documents/{test_doc_id}/comments', 'POST', {'text': 'Test comment'}, headers=AUTH)
test("Add comment", not com.get('error'))
time.sleep(0.5)

# Tags
tags = api('/api/tags', headers=AUTH)
test("Tags", isinstance(tags, list) and len(tags) > 0, f"count={len(tags) if isinstance(tags, list) else 0}")
time.sleep(0.5)

# Users
users = api('/api/users', headers=AUTH)
test("Users list", isinstance(users, list) and len(users) > 0, f"count={len(users) if isinstance(users, list) else 0}")
time.sleep(0.5)

# Tasks
task = api('/api/tasks', 'POST', {
    'title': 'Test task', 'assignee_id': user_id, 'priority': 'high', 'deadline': '2026-07-30'
}, headers=AUTH)
test("Create task", 'id' in task, f"id={task.get('id', '?')}")
task_id = task.get('id', 0)
time.sleep(0.5)

tu = api(f'/api/tasks/{task_id}', 'PUT', {'status': 'completed'}, headers=UAUTH)
test("Complete task", tu.get('status') == 'completed')
time.sleep(0.5)

# Notifications
notifs = api('/api/notifications', headers=AUTH)
test("Notifications", isinstance(notifs, list), f"count={len(notifs) if isinstance(notifs, list) else 0}")
time.sleep(0.5)

# Search
search = api('/api/documents/search?q=test', headers=AUTH)
test("Search", 'results' in search, f"count={len(search.get('results', []))}")
time.sleep(0.5)

# Reports
rep = api('/api/reports?date_from=2024-01-01&date_to=2027-12-31', headers=AUTH)
test("Reports", isinstance(rep, dict) and 'total' in rep, f"total={rep.get('total', 0)}")
test("Reports by_author", 'by_author' in rep if isinstance(rep, dict) else False)
time.sleep(0.5)

# Reports CSV
csv_r = api('/api/reports/export/csv?date_from=2024-01-01&date_to=2027-12-31', headers=AUTH, raw=True)
test("Reports CSV", csv_r.get('status') == 200, f"size={csv_r.get('length', 0)}b")
time.sleep(0.5)

# Routes
routes = api('/api/routes', headers=AUTH)
test("Routes", isinstance(routes, list), f"count={len(routes) if isinstance(routes, list) else 0}")
time.sleep(0.5)

# Templates
tmpls = api('/api/templates', headers=AUTH)
test("Templates", isinstance(tmpls, list), f"count={len(tmpls) if isinstance(tmpls, list) else 0}")
time.sleep(0.5)

# Audit log
audit = api('/api/audit-log?limit=5', headers=AUTH)
test("Audit log", isinstance(audit, list), f"count={len(audit) if isinstance(audit, list) else 0}")
time.sleep(0.5)

# Journal (correspondence)
journal = api('/api/documents/correspondence?direction=incoming', headers=AUTH)
test("Journal incoming", isinstance(journal, dict) and 'results' in journal, f"count={len(journal.get('results',[])) if isinstance(journal, dict) else 0}")
time.sleep(0.5)

# Nomenclature
nom = api('/api/nomenclature', headers=AUTH)
test("Nomenclature", isinstance(nom, list), f"count={len(nom) if isinstance(nom, list) else 0}")
time.sleep(0.5)

# Archive
arch = api(f'/api/documents/{test_doc_id}/archive', 'POST', headers=AUTH)
test("Archive doc", arch.get('status') == 'archived' or arch.get('ok'))
time.sleep(0.5)

# Trash
trash = api('/api/documents/trash', headers=AUTH)
test("Trash", isinstance(trash, list), f"count={len(trash) if isinstance(trash, list) else 0}")
time.sleep(0.5)

# PWA
m = api('/static/manifest.json')
test("PWA manifest", isinstance(m, dict) and 'name' in m)
sw = api('/static/sw.js', raw=True)
test("Service worker", sw.get('status') == 200, f"size={sw.get('length', 0)}b")
time.sleep(0.5)

# 1C API (no token configured - expect 503)
r1c = api('/api/v1/1c/documents')
test("1C API (no token)", r1c.get('error') in (401, 503))
time.sleep(0.5)

# Profile
prof = api('/api/profile', 'PUT', {'user_status': 'available'}, headers=AUTH)
test("Profile update", not prof.get('error'))

# Cleanup
api(f'/api/tasks/{task_id}', 'DELETE', headers=AUTH)

print()
print("=" * 60)
print(f"RESULTS: {PASS} passed, {FAIL} failed, {PASS+FAIL} total")
print("=" * 60)
