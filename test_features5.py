#!/usr/bin/env python3
"""Test 7 features: advanced search, user stats, bulk reassign, history export, unread docs, fav templates, related suggest."""
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
print('NEW FEATURES v5 TEST')
print('=' * 60)

# Login
r = api('/api/login', 'POST', {'login':'admedo','password':'admin123'})
test('Login admin', 'access_token' in r)
token = r.get('access_token', '')
AUTH = {'Authorization': f'Bearer {token}'}
time.sleep(0.5)

# Create test docs
d1 = api('/api/documents', 'POST', {
    'title': 'Adv search test doc', 'doc_type': 'memo', 'content': 'UniqueSearchContent12345',
    'status': 'draft', 'priority': 'high'
}, headers=AUTH)
d1_id = d1.get('id', 0)
test('Create test doc', d1_id > 0, f"id={d1_id}")
time.sleep(0.5)

# =================== 1. ADVANCED SEARCH ===================
print('\n--- Advanced Search ---')

sr = api('/api/search/advanced?q=UniqueSearchContent12345', headers=AUTH)
test('Search by text', sr.get('count', 0) >= 1, f"count={sr.get('count',0)}")
has_doc = any(i.get('id') == d1_id for i in sr.get('items', []))
test('Found test doc', has_doc)
time.sleep(0.3)

sr2 = api('/api/search/advanced?doc_type=memo&priority=high', headers=AUTH)
test('Search by type+priority', sr2.get('count', 0) >= 1, f"count={sr2.get('count',0)}")
time.sleep(0.3)

sr3 = api('/api/search/advanced?status=draft&date_from=2020-01-01', headers=AUTH)
test('Search with date filter', sr3.get('count', 0) >= 1, f"count={sr3.get('count',0)}")
time.sleep(0.5)

# =================== 2. USER STATS (ADMIN) ===================
print('\n--- User Stats ---')

# Get current user id
me = api('/api/me', headers=AUTH)
my_id = me.get('id', 1)

us = api(f'/api/users/{my_id}/stats', headers=AUTH)
test('User stats', isinstance(us, dict) and 'total_docs' in us, f"docs={us.get('total_docs',0)}")
test('Stats has by_status', 'by_status' in us)
test('Stats has user_name', 'user_name' in us)
test('Stats has tasks', 'tasks_total' in us and 'tasks_done' in us)
test('Stats has comments', 'comments_count' in us)
time.sleep(0.5)

# =================== 3. BULK REASSIGN ===================
print('\n--- Bulk Reassign ---')

# Create 2 docs to reassign
rd1 = api('/api/documents', 'POST', {
    'title': 'Reassign1', 'doc_type': 'memo', 'content': 'c1', 'status': 'draft', 'priority': 'normal'
}, headers=AUTH)
rd2 = api('/api/documents', 'POST', {
    'title': 'Reassign2', 'doc_type': 'memo', 'content': 'c2', 'status': 'draft', 'priority': 'normal'
}, headers=AUTH)
rd1_id = rd1.get('id', 0)
rd2_id = rd2.get('id', 0)
time.sleep(0.3)

# Get another user
users = api('/api/users', headers=AUTH)
other_id = None
if isinstance(users, list):
    for u in users:
        if u.get('id') != my_id:
            other_id = u['id']
            break
test('Found other user', other_id is not None, f"id={other_id}")

if other_id:
    ra = api('/api/documents/bulk-reassign', 'POST', {
        'doc_ids': [rd1_id, rd2_id], 'new_author_id': other_id
    }, headers=AUTH)
    test('Bulk reassign', ra.get('affected') == 2, f"affected={ra.get('affected',0)}")
    test('New author name', 'new_author' in ra and ra.get('new_author') != '')
else:
    test('Bulk reassign', False, 'no other user')
    test('New author name', False, 'no other user')
time.sleep(0.5)

# =================== 4. HISTORY EXPORT ===================
print('\n--- History Export ---')

he = api(f'/api/documents/{d1_id}/history/export', headers=AUTH, raw=True)
test('History export', he.get('status') == 200 and he.get('length', 0) > 20, f"size={he.get('length',0)}b")
time.sleep(0.5)

# =================== 5. UNREAD DOCUMENTS ===================
print('\n--- Unread Documents ---')

unread = api('/api/unread-docs', headers=AUTH)
test('Unread docs', isinstance(unread, dict) and 'count' in unread, f"count={unread.get('count',0)}")
test('Unread has items', isinstance(unread.get('items'), list))
time.sleep(0.5)

# =================== 6. FAVORITE TEMPLATES ===================
print('\n--- Favorite Templates ---')

# Get existing templates
tmpls = api('/api/templates', headers=AUTH)
tmpl_id = None
if isinstance(tmpls, list) and len(tmpls) > 0:
    tmpl_id = tmpls[0].get('id')

test('Has templates', tmpl_id is not None, f"id={tmpl_id}")

if tmpl_id:
    ft = api(f'/api/templates/{tmpl_id}/favorite', 'POST', headers=AUTH)
    test('Add fav template', ft.get('favorite') == True)
    time.sleep(0.3)

    fl = api('/api/templates/favorites', headers=AUTH)
    test('List fav templates', isinstance(fl, list) and tmpl_id in fl, f"ids={fl}")
    time.sleep(0.3)

    fu = api(f'/api/templates/{tmpl_id}/favorite', 'DELETE', headers=AUTH)
    test('Remove fav template', fu.get('favorite') == False)
    time.sleep(0.3)

    fl2 = api('/api/templates/favorites', headers=AUTH)
    test('Not fav after remove', isinstance(fl2, list) and tmpl_id not in fl2)
else:
    test('Add fav template', False, 'no templates')
    test('List fav templates', False, 'no templates')
    test('Remove fav template', False, 'no templates')
    test('Not fav after remove', False, 'no templates')
time.sleep(0.5)

# =================== 7. RELATED SUGGEST ===================
print('\n--- Related Suggest ---')

rs = api(f'/api/documents/{d1_id}/related-suggest', headers=AUTH)
test('Related suggest', 'suggestions' in rs, f"count={len(rs.get('suggestions',[]))}")
test('Suggestions is list', isinstance(rs.get('suggestions'), list))
if rs.get('suggestions'):
    test('Suggestion has fields', all(k in rs['suggestions'][0] for k in ['id', 'title', 'doc_type']))
else:
    test('Suggestion has fields', True, 'empty but valid')
time.sleep(0.5)

# =================== 8. FRONTEND CHECKS ===================
print('\n--- Frontend ---')

req = urllib.request.Request(BASE + '/')
resp = urllib.request.urlopen(req, timeout=10)
html = resp.read().decode()

test('Unread nav', 'unread' in html and 'renderUnread' in html)
test('Advanced search nav', 'advsearch' in html and 'renderAdvSearch' in html)
test('Advanced search form', 'doAdvSearch' in html)
test('User stats (showUserStats)', 'showUserStats' in html)
test('Bulk reassign (bulkReassign)', 'bulkReassign' in html)
test('History export (exportHistory)', 'exportHistory' in html)
test('Favorite templates (toggleFavTemplate)', 'toggleFavTemplate' in html)
test('Load fav templates (loadFavTemplates)', 'loadFavTemplates' in html)
test('Related suggest (showRelatedSuggest)', 'showRelatedSuggest' in html)

# Cleanup
api(f'/api/documents/{d1_id}', 'DELETE', headers=AUTH)
api(f'/api/documents/{rd1_id}', 'DELETE', headers=AUTH)
api(f'/api/documents/{rd2_id}', 'DELETE', headers=AUTH)

print()
print('=' * 60)
print(f'RESULTS: {PASS} passed, {FAIL} failed, {PASS+FAIL} total')
print('=' * 60)
