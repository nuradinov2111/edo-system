#!/usr/bin/env python3
"""Test all new features."""
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
print('NEW FEATURES TEST')
print('=' * 60)

# Login admin
r = api('/api/login', 'POST', {'login':'admedo','password':'admin123'})
test('Login admin', 'access_token' in r)
token = r.get('access_token', '')
AUTH = {'Authorization': f'Bearer {token}'}
time.sleep(0.5)

# Main page loads
page = api('/', raw=True)
test('Main page loads', page.get('status') == 200, f"size={page.get('length',0)}b")
time.sleep(0.3)

# Get HTML for frontend checks
req = urllib.request.Request(BASE + '/')
resp = urllib.request.urlopen(req, timeout=10)
html = resp.read().decode()

# Chart.js CDN
test('Chart.js CDN in HTML', 'chart.js' in html)

# Dashboard
dash = api('/api/dashboard', headers=AUTH)
test('Dashboard', isinstance(dash, dict) and 'total' in dash, f"total={dash.get('total',0)}")
time.sleep(0.5)

# =================== NEW FEATURES ===================

# KPI endpoint
kpi = api('/api/kpi', headers=AUTH)
test('KPI endpoint', isinstance(kpi, list) and len(kpi) > 0, f"users={len(kpi) if isinstance(kpi,list) else 0}")
if isinstance(kpi, list) and len(kpi) > 0:
    u = kpi[0]
    test('KPI fields', all(k in u for k in ['name','docs_created','approvals_done','tasks_done','avg_approval_hours']))
time.sleep(0.5)

# Bulk approve (empty - should error 400)
ba = api('/api/documents/bulk-approve', 'POST', {'doc_ids':[], 'comment':'test'}, headers=AUTH)
test('Bulk approve (empty=400)', ba.get('error') == 400)
time.sleep(0.5)

# Create doc, edit for versions, then diff
new_doc = api('/api/documents', 'POST', {
    'title': 'Diff test doc', 'doc_type': 'memo', 'content': 'Version 1 content line1\nline2\nline3',
    'description': 'Test diff', 'status': 'draft', 'priority': 'normal'
}, headers=AUTH)
test('Create doc for diff', 'id' in new_doc, f"id={new_doc.get('id','?')}")
did = new_doc.get('id', 0)
time.sleep(0.5)

# Edit to create version
api(f'/api/documents/{did}', 'PUT', {
    'title': 'Diff test doc v2', 'doc_type': 'memo', 'content': 'Version 2 changed\nline2\nline3 modified',
    'description': 'Test diff', 'status': 'draft', 'priority': 'normal',
    'tag_ids':[], 'approver_ids':[], 'related_doc_ids':[], 'attachments':[]
}, headers=AUTH)
time.sleep(0.5)

# Diff endpoint
diff = api(f'/api/documents/{did}/diff', headers=AUTH)
test('Diff endpoint', 'lines' in diff, f"lines={len(diff.get('lines',[]))}")
has_diff = any(l.get('type') in ('added','removed') for l in diff.get('lines',[]))
test('Diff shows changes', has_diff)
time.sleep(0.5)

# iCal export
ical = api('/api/calendar.ics', headers=AUTH, raw=True)
test('iCal export', ical.get('status') == 200, f"size={ical.get('length',0)}b")
time.sleep(0.5)

# Webhooks CRUD
wh_list = api('/api/webhooks', headers=AUTH)
test('Webhooks list', isinstance(wh_list, list))
time.sleep(0.3)

wh_new = api('/api/webhooks', 'POST', {'url':'https://example.com/hook','events':['all']}, headers=AUTH)
test('Create webhook', 'id' in wh_new, f"id={wh_new.get('id','?')}")
wh_id = wh_new.get('id', 0)
time.sleep(0.3)

wh_del = api(f'/api/webhooks/{wh_id}', 'DELETE', headers=AUTH)
test('Delete webhook', wh_del.get('ok') == True)
time.sleep(0.5)

# Backup
backup = api('/api/backup', headers=AUTH, raw=True)
test('Backup download', backup.get('status') == 200 and backup.get('length', 0) > 1000, f"size={backup.get('length',0)}b")
time.sleep(0.5)

# Analytics PDF
apdf = api('/api/analytics/export/pdf', headers=AUTH, raw=True)
test('Analytics PDF', apdf.get('status') == 200 and apdf.get('length', 0) > 1000, f"size={apdf.get('length',0)}b")
time.sleep(0.5)

# @mention in comment
com = api(f'/api/documents/{did}/comments', 'POST', {'text': 'Привет @usredo посмотри'}, headers=AUTH)
test('@mention comment', not com.get('error'))
time.sleep(0.5)

# Check mention notification for user
r2 = api('/api/login', 'POST', {'login':'usredo','password':'user123'})
utoken = r2.get('access_token', '')
UAUTH = {'Authorization': f'Bearer {utoken}'}
time.sleep(0.3)
notifs = api('/api/notifications', headers=UAUTH)
has_mention = False
if isinstance(notifs, list):
    for n in notifs:
        if n.get('notif_type') == 'mention':
            has_mention = True
            break
test('@mention notification received', has_mention)
time.sleep(0.5)

# Bulk approve - create pending doc and approve
uid = r2.get('user', {}).get('id', 7)
new_pending = api('/api/documents', 'POST', {
    'title': 'Bulk approve test', 'doc_type': 'memo', 'content': 'Bulk test',
    'description': 'Test', 'status': 'pending', 'priority': 'normal',
    'approver_ids': [1]
}, headers=UAUTH)
pdid = new_pending.get('id', 0)
test('Create pending doc', pdid > 0, f"id={pdid}")
time.sleep(0.5)

ba2 = api('/api/documents/bulk-approve', 'POST', {'doc_ids':[pdid], 'comment':'Mass OK'}, headers=AUTH)
test('Bulk approve works', ba2.get('approved', 0) >= 1, f"approved={ba2.get('approved',0)}")
time.sleep(0.5)

# =================== FRONTEND CHECKS ===================

test('Kanban DnD (kanbanDragStart)', 'kanbanDragStart' in html)
test('Kanban DnD (kanbanDrop)', 'kanbanDrop' in html)
test('Dashboard widgets toggle', 'toggleDashWidgets' in html)
test('Dashboard widget config', 'toggleWidget' in html)
test('Diff viewer (showDiff)', 'showDiff' in html)
test('Mention autocomplete', 'mentionDropdown' in html and 'insertMention' in html)
test('Notification polling 30s', 'setInterval' in html and '30000' in html)
test('Bulk approve button', 'bulkApproveAll' in html)
test('KPI button (loadKPI)', 'loadKPI' in html)
test('Analytics PDF button', 'exportAnalyticsPDF' in html)
test('Webhook settings UI', 'showWebhookSettings' in html)
test('iCal link in page', 'calendar.ics' in html)
test('Backup link in page', '/api/backup' in html)
test('Chart.js canvas (chartMonthly)', 'chartMonthly' in html)
test('Chart.js canvas (chartStatus)', 'chartStatus' in html)
test('KPI section container', 'kpiSection' in html)

# Cleanup
api(f'/api/documents/{did}', 'DELETE', headers=AUTH)
api(f'/api/documents/{pdid}', 'DELETE', headers=AUTH)

print()
print('=' * 60)
print(f'RESULTS: {PASS} passed, {FAIL} failed, {PASS+FAIL} total')
print('=' * 60)
