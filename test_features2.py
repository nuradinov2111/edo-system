#!/usr/bin/env python3
"""Test 7 new features: favorites, delegations, signatures, template vars, views, bulk ops, xlsx."""
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
print('NEW FEATURES v2 TEST')
print('=' * 60)

# Login admin
r = api('/api/login', 'POST', {'login':'admedo','password':'admin123'})
test('Login admin', 'access_token' in r)
token = r.get('access_token', '')
admin_id = r.get('user', {}).get('id', 1)
AUTH = {'Authorization': f'Bearer {token}'}
time.sleep(0.5)

# Login user
r2 = api('/api/login', 'POST', {'login':'usredo','password':'user123'})
test('Login user', 'access_token' in r2)
user_token = r2.get('access_token', '')
user_id = r2.get('user', {}).get('id', 7)
UAUTH = {'Authorization': f'Bearer {user_token}'}
time.sleep(0.5)

# Create test document
new_doc = api('/api/documents', 'POST', {
    'title': 'Test features v2', 'doc_type': 'memo', 'content': 'Test content for signatures',
    'description': 'Testing', 'status': 'draft', 'priority': 'normal'
}, headers=AUTH)
test('Create test doc', 'id' in new_doc, f"id={new_doc.get('id','?')}")
doc_id = new_doc.get('id', 0)
time.sleep(0.5)

# =================== 1. FAVORITES ===================
print('\n--- Favorites ---')

fav = api(f'/api/documents/{doc_id}/favorite', 'POST', headers=AUTH)
test('Add favorite', fav.get('favorited') == True)
time.sleep(0.3)

is_fav = api(f'/api/documents/{doc_id}/is-favorite', headers=AUTH)
test('Is favorite', is_fav.get('favorited') == True)
time.sleep(0.3)

favs = api('/api/favorites', headers=AUTH)
test('List favorites', isinstance(favs, list) and len(favs) > 0, f"count={len(favs) if isinstance(favs, list) else 0}")
time.sleep(0.3)

unfav = api(f'/api/documents/{doc_id}/favorite', 'DELETE', headers=AUTH)
test('Remove favorite', unfav.get('favorited') == False)
time.sleep(0.3)

is_fav2 = api(f'/api/documents/{doc_id}/is-favorite', headers=AUTH)
test('Not favorite after remove', is_fav2.get('favorited') == False)
time.sleep(0.5)

# =================== 2. DELEGATIONS ===================
print('\n--- Delegations ---')

deg = api('/api/delegations', 'POST', {
    'to_user_id': user_id, 'date_from': '2026-07-20', 'date_to': '2026-07-30', 'reason': 'Отпуск'
}, headers=AUTH)
test('Create delegation', 'id' in deg, f"id={deg.get('id','?')}")
deg_id = deg.get('id', 0)
time.sleep(0.3)

degs = api('/api/delegations', headers=AUTH)
test('List delegations', isinstance(degs, list) and len(degs) > 0, f"count={len(degs) if isinstance(degs, list) else 0}")
has_new = any(d.get('id') == deg_id for d in degs) if isinstance(degs, list) else False
test('New delegation in list', has_new)
time.sleep(0.3)

del_deg = api(f'/api/delegations/{deg_id}', 'DELETE', headers=AUTH)
test('Delete delegation', del_deg.get('ok') == True)
time.sleep(0.5)

# =================== 3. DIGITAL SIGNATURE ===================
print('\n--- Digital Signature ---')

sig = api(f'/api/documents/{doc_id}/sign', 'POST', headers=AUTH)
test('Sign document', sig.get('ok') == True and 'hash' in sig, f"hash={sig.get('hash','')[:16]}...")
time.sleep(0.3)

sigs = api(f'/api/documents/{doc_id}/signatures', headers=AUTH)
test('Get signatures', isinstance(sigs, list) and len(sigs) > 0, f"count={len(sigs) if isinstance(sigs, list) else 0}")
time.sleep(0.3)

ver = api(f'/api/documents/{doc_id}/verify', headers=AUTH)
test('Verify signatures (valid)', ver.get('verified') == True)
test('Verify message', ver.get('message') == 'Все подписи верны')
time.sleep(0.5)

# =================== 4. TEMPLATE VARIABLES ===================
print('\n--- Template Variables ---')

# Create template with variables
tmpl = api('/api/templates', 'POST', {
    'name': 'Test template vars', 'doc_type': 'memo',
    'title_template': 'Приказ №{{number}} от {{date}}',
    'content_template': 'Уважаемый {{name}}, приказываю {{action}}',
    'is_public': True
}, headers=AUTH)
test('Create template with vars', 'id' in tmpl, f"id={tmpl.get('id','?')}")
tmpl_id = tmpl.get('id', 0)
time.sleep(0.3)

tvars = api(f'/api/templates/{tmpl_id}/variables', headers=AUTH)
test('Get template variables', 'variables' in tvars, f"vars={tvars.get('variables', [])}")
test('Has expected vars', set(tvars.get('variables', [])) == {'number', 'date', 'name', 'action'})
time.sleep(0.3)

filled = api(f'/api/templates/{tmpl_id}/fill', 'POST', {
    'variables': {'number': '42', 'date': '22.07.2026', 'name': 'Иванов', 'action': 'выполнить работу'}
}, headers=AUTH)
test('Fill template', 'title' in filled)
test('Fill title correct', filled.get('title') == 'Приказ №42 от 22.07.2026')
test('Fill content correct', 'Уважаемый Иванов' in filled.get('content', ''))
test('No unfilled vars', len(filled.get('unfilled_variables', [])) == 0)
time.sleep(0.5)

# =================== 5. VIEW TRACKING ===================
print('\n--- View Tracking ---')

view = api(f'/api/documents/{doc_id}/view', 'POST', headers=AUTH)
test('Record view', view.get('ok') == True)
time.sleep(0.3)

# View as another user
api(f'/api/documents/{doc_id}/view', 'POST', headers=UAUTH)
time.sleep(0.3)

views = api(f'/api/documents/{doc_id}/views', headers=AUTH)
test('Get views', 'views' in views and views.get('count', 0) >= 2, f"count={views.get('count', 0)}")
time.sleep(0.5)

# =================== 6. BULK OPERATIONS ===================
print('\n--- Bulk Operations ---')

# Create 2 docs for bulk
d1 = api('/api/documents', 'POST', {'title':'Bulk1','doc_type':'memo','content':'c1','status':'draft','priority':'normal'}, headers=AUTH)
d2 = api('/api/documents', 'POST', {'title':'Bulk2','doc_type':'memo','content':'c2','status':'draft','priority':'normal'}, headers=AUTH)
d1_id = d1.get('id', 0)
d2_id = d2.get('id', 0)
test('Create bulk docs', d1_id > 0 and d2_id > 0, f"ids={d1_id},{d2_id}")
time.sleep(0.3)

# Bulk archive
ba = api('/api/documents/bulk-action', 'POST', {'doc_ids': [d1_id, d2_id], 'action': 'archive'}, headers=AUTH)
test('Bulk archive', ba.get('affected', 0) == 2, f"affected={ba.get('affected', 0)}")
time.sleep(0.3)

# Bulk restore
br = api('/api/documents/bulk-action', 'POST', {'doc_ids': [d1_id, d2_id], 'action': 'restore'}, headers=AUTH)
test('Bulk restore', br.get('affected', 0) == 2)
time.sleep(0.3)

# Bulk add tags
tags = api('/api/tags', headers=AUTH)
tag_id = tags[0]['id'] if isinstance(tags, list) and len(tags) > 0 else 1
bt = api('/api/documents/bulk-action', 'POST', {'doc_ids': [d1_id, d2_id], 'action': 'add_tags', 'tag_ids': [tag_id]}, headers=AUTH)
test('Bulk add tags', bt.get('affected', 0) == 2)
time.sleep(0.3)

# Bulk delete
bd = api('/api/documents/bulk-action', 'POST', {'doc_ids': [d1_id, d2_id], 'action': 'delete'}, headers=AUTH)
test('Bulk delete', bd.get('affected', 0) == 2)
time.sleep(0.3)

# Bad action
bb = api('/api/documents/bulk-action', 'POST', {'doc_ids': [1], 'action': 'invalid'}, headers=AUTH)
test('Bulk bad action (400)', bb.get('error') == 400)
time.sleep(0.5)

# =================== 7. XLSX EXPORT ===================
print('\n--- XLSX Export ---')

xlsx = api('/api/reports/export/xlsx?date_from=2024-01-01&date_to=2027-12-31', headers=AUTH, raw=True)
test('XLSX export', xlsx.get('status') == 200 and xlsx.get('length', 0) > 1000, f"size={xlsx.get('length', 0)}b")
time.sleep(0.5)

# =================== FRONTEND CHECKS ===================
print('\n--- Frontend ---')

req = urllib.request.Request(BASE + '/')
resp = urllib.request.urlopen(req, timeout=10)
html = resp.read().decode()

test('Favorites nav', 'favorites' in html and 'renderFavorites' in html)
test('Delegations nav', 'delegations' in html and 'renderDelegations' in html)
test('Sign button', 'signDocument' in html)
test('Verify button', 'verifyDocument' in html)
test('View tracking', 'recordDocView' in html and 'showDocViews' in html)
test('Fill template', 'fillTemplate' in html and 'submitTemplateFill' in html)
test('Bulk add tags', 'bulkAddTags' in html and 'bulkActionNew' in html)
test('XLSX export button', 'exportReportXLSX' in html)
test('Delegation form', 'createDelegation' in html and 'deleteDelegation' in html)

# Cleanup
api(f'/api/documents/{doc_id}', 'DELETE', headers=AUTH)
api(f'/api/templates/{tmpl_id}', 'DELETE', headers=AUTH)

print()
print('=' * 60)
print(f'RESULTS: {PASS} passed, {FAIL} failed, {PASS+FAIL} total')
print('=' * 60)
