#!/usr/bin/env python3
"""Test 7 features: reminders, controlled docs, dept stats, zip export, autosave, pinned, compare."""
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
print('NEW FEATURES v4 TEST')
print('=' * 60)

# Login
r = api('/api/login', 'POST', {'login':'admedo','password':'admin123'})
test('Login admin', 'access_token' in r)
token = r.get('access_token', '')
AUTH = {'Authorization': f'Bearer {token}'}
time.sleep(0.5)

# Create test docs
d1 = api('/api/documents', 'POST', {
    'title': 'Compare doc 1', 'doc_type': 'memo', 'content': 'Line1\nLine2\nLine3',
    'status': 'draft', 'priority': 'normal'
}, headers=AUTH)
d2 = api('/api/documents', 'POST', {
    'title': 'Compare doc 2', 'doc_type': 'memo', 'content': 'Line1\nChanged\nLine3',
    'status': 'draft', 'priority': 'normal'
}, headers=AUTH)
d1_id = d1.get('id', 0)
d2_id = d2.get('id', 0)
test('Create test docs', d1_id > 0 and d2_id > 0, f"ids={d1_id},{d2_id}")
time.sleep(0.5)

# =================== 1. REMINDERS ===================
print('\n--- Reminders ---')

rem = api('/api/reminders', 'POST', {
    'document_id': d1_id, 'remind_at': '2026-12-31T10:00', 'message': 'Проверить документ'
}, headers=AUTH)
test('Create reminder', 'id' in rem, f"id={rem.get('id','?')}")
rem_id = rem.get('id', 0)
time.sleep(0.3)

rems = api('/api/reminders', headers=AUTH)
test('List reminders', isinstance(rems, list) and len(rems) > 0, f"count={len(rems) if isinstance(rems, list) else 0}")
has_new = any(r.get('id') == rem_id for r in rems) if isinstance(rems, list) else False
test('New reminder in list', has_new)
time.sleep(0.3)

del_rem = api(f'/api/reminders/{rem_id}', 'DELETE', headers=AUTH)
test('Delete reminder', del_rem.get('ok') == True)
time.sleep(0.5)

# =================== 2. CONTROLLED DOCS ===================
print('\n--- Controlled Docs ---')

ctrl = api(f'/api/documents/{d1_id}/control', 'POST', {'note': 'Важный документ'}, headers=AUTH)
test('Add to control', ctrl.get('controlled') == True)
time.sleep(0.3)

is_ctrl = api(f'/api/documents/{d1_id}/is-controlled', headers=AUTH)
test('Is controlled', is_ctrl.get('controlled') == True)
time.sleep(0.3)

ctrls = api('/api/control', headers=AUTH)
test('List controlled', isinstance(ctrls, list) and len(ctrls) > 0, f"count={len(ctrls) if isinstance(ctrls, list) else 0}")
time.sleep(0.3)

rm_ctrl = api(f'/api/documents/{d1_id}/control', 'DELETE', headers=AUTH)
test('Remove from control', rm_ctrl.get('controlled') == False)
time.sleep(0.3)

is_ctrl2 = api(f'/api/documents/{d1_id}/is-controlled', headers=AUTH)
test('Not controlled after remove', is_ctrl2.get('controlled') == False)
time.sleep(0.5)

# =================== 3. DEPARTMENT STATS ===================
print('\n--- Department Stats ---')

ds = api('/api/department-stats', headers=AUTH)
test('Department stats', isinstance(ds, list) and len(ds) > 0, f"depts={len(ds) if isinstance(ds, list) else 0}")
if isinstance(ds, list) and len(ds) > 0:
    d = ds[0]
    test('Dept has fields', all(k in d for k in ['name', 'users', 'docs', 'approvals', 'tasks_done', 'tasks_total']))
time.sleep(0.5)

# =================== 4. EXPORT ZIP ===================
print('\n--- Export ZIP ---')

zp = api('/api/documents/export-zip', 'POST', {'doc_ids': [d1_id, d2_id]}, headers=AUTH, raw=True)
test('Export ZIP', zp.get('status') == 200 and zp.get('length', 0) > 100, f"size={zp.get('length', 0)}b")
time.sleep(0.3)

zp_empty = api('/api/documents/export-zip', 'POST', {'doc_ids': []}, headers=AUTH)
test('Export ZIP empty (400)', zp_empty.get('error') == 400)
time.sleep(0.5)

# =================== 5. PINNED DOCS ===================
print('\n--- Pinned Docs ---')

pin = api(f'/api/documents/{d1_id}/pin', 'POST', headers=AUTH)
test('Pin document', pin.get('pinned') == True)
time.sleep(0.3)

pins = api('/api/pinned', headers=AUTH)
test('List pinned', isinstance(pins, list) and d1_id in pins, f"pinned={pins}")
time.sleep(0.3)

unpin = api(f'/api/documents/{d1_id}/pin', 'DELETE', headers=AUTH)
test('Unpin document', unpin.get('pinned') == False)
time.sleep(0.3)

pins2 = api('/api/pinned', headers=AUTH)
test('Not pinned after remove', isinstance(pins2, list) and d1_id not in pins2)
time.sleep(0.5)

# =================== 6. COMPARE DOCUMENTS ===================
print('\n--- Compare Documents ---')

cmp = api(f'/api/compare-docs?id1={d1_id}&id2={d2_id}', headers=AUTH)
test('Compare docs', 'diff' in cmp and 'doc1' in cmp and 'doc2' in cmp)
test('Compare has diff lines', isinstance(cmp.get('diff'), list) and len(cmp.get('diff', [])) > 0)
has_change = any(l.get('type') == 'changed' for l in cmp.get('diff', []))
test('Compare finds changes', has_change)
time.sleep(0.5)

# =================== 7. FRONTEND CHECKS ===================
print('\n--- Frontend ---')

req = urllib.request.Request(BASE + '/')
resp = urllib.request.urlopen(req, timeout=10)
html = resp.read().decode()

test('Reminders nav', 'reminders' in html and 'renderReminders' in html)
test('Set reminder (setReminder)', 'setReminder' in html)
test('Controlled nav', 'controlled' in html and 'renderControlled' in html)
test('Toggle control (toggleControl)', 'toggleControl' in html)
test('Dept stats nav', 'deptstats' in html and 'renderDeptStats' in html)
test('Export ZIP (exportSelectedZip)', 'exportSelectedZip' in html)
test('Pinned docs (togglePin)', 'togglePin' in html and 'pinnedIds' in html)
test('Compare docs (compareWithDoc)', 'compareWithDoc' in html)
test('Autosave (startAutosave)', 'startAutosave' in html and 'restoreAutosave' in html)
test('Clear autosave (clearAutosave)', 'clearAutosave' in html)
test('Pinned indicator (128204)', '128204' in html)

# Cleanup
api(f'/api/documents/{d1_id}', 'DELETE', headers=AUTH)
api(f'/api/documents/{d2_id}', 'DELETE', headers=AUTH)

print()
print('=' * 60)
print(f'RESULTS: {PASS} passed, {FAIL} failed, {PASS+FAIL} total')
print('=' * 60)
