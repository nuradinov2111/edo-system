#!/usr/bin/env python3
"""Test 7 features: desktop notifs, rollback, barcode, shortcuts, my-stats, comment files, batch print."""
import urllib.request, json, time

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
        return {'error': e.code, 'detail': e.read().decode()[:300]}
    except Exception as e:
        return {'error': str(e)}

def test(name, ok, detail=''):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f'  PASS [{PASS+FAIL:02d}] {name} {detail}')
    else:
        FAIL += 1
        print(f'  FAIL [{PASS+FAIL:02d}] {name} {detail}')

print('=' * 60)
print('NEW FEATURES v3 TEST')
print('=' * 60)

# Login
r = api('/api/login', 'POST', {'login':'admedo','password':'admin123'})
test('Login admin', 'access_token' in r)
token = r.get('access_token', '')
AUTH = {'Authorization': f'Bearer {token}'}
time.sleep(0.5)

# Create test doc
doc = api('/api/documents', 'POST', {
    'title': 'Test v3 original', 'doc_type': 'memo', 'content': 'Original content v1',
    'description': 'Testing', 'status': 'draft', 'priority': 'normal'
}, headers=AUTH)
test('Create test doc', 'id' in doc, f"id={doc.get('id','?')}")
doc_id = doc.get('id', 0)
time.sleep(0.5)

# Edit to create a version
api(f'/api/documents/{doc_id}', 'PUT', {
    'title': 'Test v3 edited', 'doc_type': 'memo', 'content': 'Edited content v2',
    'description': 'Testing', 'status': 'draft', 'priority': 'normal',
    'tag_ids': [], 'approver_ids': [], 'related_doc_ids': [], 'attachments': []
}, headers=AUTH)
time.sleep(0.5)

# =================== 1. VERSION ROLLBACK ===================
print('\n--- Version Rollback ---')

# Get doc to find version id
d = api(f'/api/documents/{doc_id}', headers=AUTH)
versions = d.get('versions', [])
test('Has version', len(versions) > 0, f"versions={len(versions)}")

if versions:
    ver_id = versions[0]['id']
    rb = api(f'/api/documents/{doc_id}/rollback/{ver_id}', 'POST', headers=AUTH)
    test('Rollback success', rb.get('title') == 'Test v3 original')
    test('Rollback content', rb.get('content') == 'Original content v1')
else:
    test('Rollback success', False, 'no versions')
    test('Rollback content', False, 'no versions')
time.sleep(0.5)

# =================== 2. BARCODE ===================
print('\n--- Barcode ---')

bc = api(f'/api/documents/{doc_id}/barcode', headers=AUTH)
test('Barcode', 'barcode_base64' in bc, f"code={bc.get('code','?')}")
test('Barcode has data', len(bc.get('barcode_base64', '')) > 100)
time.sleep(0.5)

# =================== 3. PERSONAL STATS ===================
print('\n--- Personal Stats ---')

stats = api('/api/my-stats', headers=AUTH)
test('My stats', isinstance(stats, dict) and 'total_docs' in stats, f"docs={stats.get('total_docs',0)}")
test('Stats has by_status', 'by_status' in stats)
test('Stats has approvals', 'approvals_done' in stats and 'approvals_pending' in stats)
test('Stats has tasks', 'tasks_total' in stats and 'tasks_done' in stats)
test('Stats has monthly', isinstance(stats.get('monthly'), list) and len(stats.get('monthly', [])) > 0)
test('Stats has comments', 'comments_count' in stats)
time.sleep(0.5)

# =================== 4. COMMENT WITH FILE ===================
print('\n--- Comment with File ---')

# Simple text-only comment via new endpoint
import urllib.parse
boundary = '----TestBoundary123'
body_parts = []
body_parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="text"\r\n\r\nTest comment with file endpoint')
body_str = '\r\n'.join(body_parts) + f'\r\n--{boundary}--\r\n'
body_bytes = body_str.encode()
req = urllib.request.Request(
    BASE + f'/api/documents/{doc_id}/comments/with-file',
    data=body_bytes,
    headers={**AUTH, 'Content-Type': f'multipart/form-data; boundary={boundary}'},
    method='POST'
)
try:
    resp = urllib.request.urlopen(req, timeout=30)
    cf_result = json.loads(resp.read().decode())
    test('Comment with file endpoint', 'id' in cf_result)
except Exception as e:
    test('Comment with file endpoint', False, str(e)[:100])
time.sleep(0.5)

# =================== 5. BATCH PRINT ===================
print('\n--- Batch Print ---')

# Create 2 docs
d1 = api('/api/documents', 'POST', {'title':'Print1','doc_type':'memo','content':'c1','status':'draft','priority':'normal'}, headers=AUTH)
d2 = api('/api/documents', 'POST', {'title':'Print2','doc_type':'memo','content':'c2','status':'draft','priority':'normal'}, headers=AUTH)
d1_id = d1.get('id', 0)
d2_id = d2.get('id', 0)
time.sleep(0.3)

bp = api('/api/documents/batch-print', 'POST', {'doc_ids': [d1_id, d2_id]}, headers=AUTH)
test('Batch print', bp.get('count') == 2, f"count={bp.get('count',0)}")
test('Batch print has docs', isinstance(bp.get('documents'), list) and len(bp.get('documents', [])) == 2)
if bp.get('documents'):
    test('Print doc has content', 'content' in bp['documents'][0] and 'title' in bp['documents'][0])
time.sleep(0.3)

# Too many
bp_err = api('/api/documents/batch-print', 'POST', {'doc_ids': list(range(1, 22))}, headers=AUTH)
test('Batch print limit (400)', bp_err.get('error') == 400)
time.sleep(0.5)

# =================== 6. FRONTEND CHECKS ===================
print('\n--- Frontend ---')

req = urllib.request.Request(BASE + '/')
resp = urllib.request.urlopen(req, timeout=10)
html = resp.read().decode()

test('Desktop notifications (requestDesktopNotifs)', 'requestDesktopNotifs' in html)
test('Desktop notifications (showDesktopNotif)', 'showDesktopNotif' in html)
test('Notification.permission', 'Notification' in html and 'permission' in html)
test('Version rollback (rollbackVersion)', 'rollbackVersion' in html)
test('Barcode (showBarcode)', 'showBarcode' in html)
test('Barcode print (printBarcode)', 'printBarcode' in html)
test('Keyboard shortcuts handler', 'showShortcutsHelp' in html)
test('Shortcut Ctrl+N', "case'n'" in html or "case'N'" in html)
test('My stats page (renderMyStats)', 'renderMyStats' in html)
test('My stats nav', 'mystats' in html)
test('Comment with file (addCommentWithFile)', 'addCommentWithFile' in html)
test('Submit comment file (submitCommentFile)', 'submitCommentFile' in html)
test('Batch print (batchPrint)', 'batchPrint' in html)

# Cleanup
api(f'/api/documents/{doc_id}', 'DELETE', headers=AUTH)
api(f'/api/documents/{d1_id}', 'DELETE', headers=AUTH)
api(f'/api/documents/{d2_id}', 'DELETE', headers=AUTH)

print()
print('=' * 60)
print(f'RESULTS: {PASS} passed, {FAIL} failed, {PASS+FAIL} total')
print('=' * 60)
