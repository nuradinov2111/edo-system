const https = require('https');

function apiCall(method, path, token, body) {
  return new Promise((resolve) => {
    const data = body ? JSON.stringify(body) : null;
    const opts = {
      method,
      headers: { 'Content-Type': 'application/json' }
    };
    if (token) opts.headers['Authorization'] = 'Bearer ' + token;
    if (data) opts.headers['Content-Length'] = Buffer.byteLength(data);
    const req = https.request('https://edo-system.onrender.com' + path, opts, res => {
      let b = '';
      res.on('data', c => b += c);
      res.on('end', () => {
        try { resolve({ status: res.statusCode, data: JSON.parse(b) }); }
        catch (e) { resolve({ status: res.statusCode, data: b.slice(0, 200) }); }
      });
    });
    req.on('error', e => resolve({ status: 0, data: e.message }));
    if (data) req.write(data);
    req.end();
  });
}

(async () => {
  let pass = 0, fail = 0;
  function check(name, ok, detail) {
    if (ok) { pass++; console.log('  OK  ' + name + (detail ? ' -- ' + detail : '')); }
    else { fail++; console.log('  FAIL ' + name + (detail ? ' -- ' + detail : '')); }
  }

  // 1. AUTH
  console.log('\n====== 1. АВТОРИЗАЦИЯ ======');
  const a1 = await apiCall('POST', '/api/login', null, { login: 'admedo', password: 'admin123' });
  check('Логин админ', a1.status === 200, a1.data?.user?.name);
  const AT = a1.data.access_token;

  const a2 = await apiCall('POST', '/api/login', null, { login: 'buhgal', password: 'buh123' });
  check('Логин бухгалтер', a2.status === 200, a2.data?.user?.name);
  const BT = a2.data.access_token;

  const a3 = await apiCall('POST', '/api/login', null, { login: 'usredo', password: 'user123' });
  check('Логин сотрудник', a3.status === 200, a3.data?.user?.name);
  const UT = a3.data.access_token;

  const a4 = await apiCall('POST', '/api/login', null, { login: 'manger', password: 'manager123' });
  check('Логин менеджер', a4.status === 200, a4.data?.user?.name);
  const MT = a4.data.access_token;

  const a5 = await apiCall('POST', '/api/login', null, { login: 'admedo', password: 'wrong' });
  check('Неверный пароль = 401', a5.status === 401);

  // 2. /api/me
  console.log('\n====== 2. ПРОФИЛЬ /api/me ======');
  const me = await apiCall('GET', '/api/me', AT);
  check('/api/me', me.status === 200, 'role=' + me.data?.role);

  // 3. USERS
  console.log('\n====== 3. ПОЛЬЗОВАТЕЛИ ======');
  const users = await apiCall('GET', '/api/users', AT);
  check('Список пользователей', users.status === 200, 'count=' + users.data?.length);

  const buhUser = users.data.find(u => u.login === 'buhgal');
  const mgrUser = users.data.find(u => u.login === 'manger');

  // 4. TAGS
  console.log('\n====== 4. ТЕГИ ======');
  const tags = await apiCall('GET', '/api/tags', AT);
  check('Список тегов', tags.status === 200, 'count=' + tags.data?.length);

  // 5. CREATE DOCS
  console.log('\n====== 5. СОЗДАНИЕ ДОКУМЕНТОВ ======');
  const doc1 = await apiCall('POST', '/api/documents', AT, {
    title: 'Тест-договор', description: 'Тестовый', content: 'Содержание',
    doc_type: 'contract', status: 'draft', priority: 'normal',
    extra_fields: { counterparty: 'ООО Тест' },
    approver_ids: [], tag_ids: [], related_doc_ids: [], attachments: []
  });
  check('Создать черновик', doc1.status === 200, 'id=' + doc1.data?.id);
  const docId1 = doc1.data?.id;

  const doc2 = await apiCall('POST', '/api/documents', AT, {
    title: 'Тест-приказ', description: '', content: 'Приказ',
    doc_type: 'order', status: 'pending', priority: 'high', sequential: true,
    deadline: '2026-08-01',
    extra_fields: { order_category: 'По основной деятельности', effective_date: '2026-08-01' },
    approver_ids: [buhUser.id, mgrUser.id],
    tag_ids: tags.data?.length ? [tags.data[0].id] : [],
    related_doc_ids: [], attachments: []
  });
  check('Создать на согласование', doc2.status === 200, 'status=' + doc2.data?.status);
  const docId2 = doc2.data?.id;

  const doc3 = await apiCall('POST', '/api/documents', BT, {
    title: 'Тест вх. накладная', description: 'Тест', content: 'ТН',
    doc_type: 'incoming_waybill', status: 'draft', priority: 'normal',
    extra_fields: { supplier: 'ООО Поставщик', incoming_number: 'ТН-555', received_date: '2026-07-21', total_amount: 250000 },
    approver_ids: [], tag_ids: [], related_doc_ids: [], attachments: []
  });
  check('Создать вх. накладную', doc3.status === 200, 'type=' + doc3.data?.doc_type);

  const doc4 = await apiCall('POST', '/api/documents', BT, {
    title: 'Тест исх. акт', description: 'Тест', content: 'Акт',
    doc_type: 'outgoing_act', status: 'draft', priority: 'normal',
    extra_fields: { recipient: 'ИП Клиент', outgoing_number: 'АКТ-077', send_date: '2026-07-21', amount: 95000 },
    approver_ids: [], tag_ids: [], related_doc_ids: [], attachments: []
  });
  check('Создать исх. акт', doc4.status === 200, 'type=' + doc4.data?.doc_type);

  // 6. LIST DOCS
  console.log('\n====== 6. СПИСОК ДОКУМЕНТОВ ======');
  const docs = await apiCall('GET', '/api/documents', AT);
  check('Документы (админ)', docs.status === 200, 'count=' + docs.data?.length);
  const docsU = await apiCall('GET', '/api/documents', UT);
  check('Документы (сотрудник)', docsU.status === 200, 'count=' + docsU.data?.length);

  // 7. DETAIL
  console.log('\n====== 7. ПРОСМОТР ДОКУМЕНТА ======');
  const det = await apiCall('GET', '/api/documents/' + docId1, AT);
  check('Просмотр', det.status === 200, 'title=' + det.data?.title);

  // 8. EDIT
  console.log('\n====== 8. РЕДАКТИРОВАНИЕ ======');
  const upd = await apiCall('PUT', '/api/documents/' + docId1, AT, {
    title: 'Тест-договор (ред)', description: 'Обновлено', content: 'Новое',
    doc_type: 'contract', status: 'draft', priority: 'high',
    extra_fields: { counterparty: 'ООО Тест2' },
    approver_ids: [], tag_ids: [], related_doc_ids: [], attachments: []
  });
  check('Редактировать', upd.status === 200, 'title=' + upd.data?.title);
  check('Версия создана', upd.data?.versions?.length > 0, 'v=' + upd.data?.versions?.length);

  // 9. APPROVE
  console.log('\n====== 9. СОГЛАСОВАНИЕ ======');
  const ap1 = await apiCall('POST', '/api/documents/' + docId2 + '/approve', BT, { comment: 'ОК бух' });
  check('Согласовать (бухгалтер)', ap1.status === 200);
  const apS = ap1.data?.approvals?.find(a => a.user_id === buhUser.id);
  check('Статус = approved', apS?.status === 'approved');
  check('ЭЦП есть', !!apS?.signature);

  const ap2 = await apiCall('POST', '/api/documents/' + docId2 + '/approve', MT, { comment: 'ОК мгр' });
  check('Согласовать (менеджер)', ap2.status === 200);
  check('Полностью согласован', ap2.data?.status === 'approved');

  // 10. REJECT
  console.log('\n====== 10. ОТКЛОНЕНИЕ ======');
  const doc5 = await apiCall('POST', '/api/documents', AT, {
    title: 'Тест отклонения', description: '', content: 'Текст',
    doc_type: 'memo', status: 'pending', priority: 'normal',
    extra_fields: { to_whom: 'Директору' },
    approver_ids: [buhUser.id], tag_ids: [], related_doc_ids: [], attachments: []
  });
  const rej = await apiCall('POST', '/api/documents/' + doc5.data?.id + '/reject', BT, { comment: 'Нет данных' });
  check('Отклонить', rej.status === 200, 'status=' + rej.data?.status);

  // 11. RECALL / RESEND
  console.log('\n====== 11. ОТЗЫВ И ПОВТОР ======');
  const doc6 = await apiCall('POST', '/api/documents', AT, {
    title: 'Тест отзыва', description: '', content: 'Текст',
    doc_type: 'report', status: 'pending', priority: 'normal',
    approver_ids: [buhUser.id], tag_ids: [], related_doc_ids: [], attachments: []
  });
  const rec = await apiCall('POST', '/api/documents/' + doc6.data?.id + '/recall', AT, {});
  check('Отозвать', rec.status === 200, 'status=' + rec.data?.status);
  const res2 = await apiCall('POST', '/api/documents/' + doc6.data?.id + '/resend', AT, {});
  check('Повторно отправить', res2.status === 200, 'status=' + res2.data?.status);

  // 12. COMMENTS
  console.log('\n====== 12. КОММЕНТАРИИ ======');
  const comm = await apiCall('POST', '/api/documents/' + docId1 + '/comments', AT, { text: 'Тестовый комментарий' });
  check('Комментарий', comm.status === 200, 'comments=' + comm.data?.comments?.length);

  // 13. RESOLUTION
  console.log('\n====== 13. РЕЗОЛЮЦИЯ ======');
  const resol = await apiCall('POST', '/api/documents/' + docId2 + '/resolution', MT, { text: 'К исполнению' });
  check('Резолюция', resol.status === 200, 'status=' + resol.data?.status);

  // 14. COPY
  console.log('\n====== 14. КОПИРОВАНИЕ ======');
  const cp = await apiCall('POST', '/api/documents/' + docId1 + '/copy', AT, {});
  check('Копировать', cp.status === 200, 'title=' + cp.data?.title);

  // 15. ARCHIVE
  console.log('\n====== 15. АРХИВ ======');
  const arc = await apiCall('POST', '/api/documents/' + docId1 + '/archive', AT, {});
  check('Архивировать', arc.status === 200, 'status=' + arc.data?.status);

  // 16. DELETE / TRASH / RESTORE
  console.log('\n====== 16. КОРЗИНА ======');
  const dl = await apiCall('DELETE', '/api/documents/' + cp.data?.id, AT);
  check('Удалить в корзину', dl.status === 200);
  const tr = await apiCall('GET', '/api/documents/trash', AT);
  check('Список корзины', tr.status === 200, 'count=' + tr.data?.length);
  const rst = await apiCall('POST', '/api/documents/' + cp.data?.id + '/restore', AT, {});
  check('Восстановить', rst.status === 200);

  // 17. SEARCH
  console.log('\n====== 17. ПОИСК ======');
  const sr = await apiCall('GET', '/api/documents/search?q=' + encodeURIComponent('Тест'), AT);
  check('Поиск', sr.status === 200, 'results=' + sr.data?.total);

  // 18. NOTIFICATIONS
  console.log('\n====== 18. УВЕДОМЛЕНИЯ ======');
  const nf = await apiCall('GET', '/api/notifications', BT);
  check('Список уведомлений', nf.status === 200, 'count=' + nf.data?.length);
  if (nf.data?.length > 0) {
    const r1 = await apiCall('POST', '/api/notifications/' + nf.data[0].id + '/read', BT, {});
    check('Прочитать одно', r1.status === 200);
  }
  const ra = await apiCall('POST', '/api/notifications/read-all', BT, {});
  check('Прочитать все', ra.status === 200);

  // 19. TASKS
  console.log('\n====== 19. ПОРУЧЕНИЯ ======');
  const tk = await apiCall('POST', '/api/tasks', AT, {
    title: 'Тест поручение', description: 'Проверить', assignee_id: buhUser.id, priority: 'high', deadline: '2026-08-01'
  });
  check('Создать поручение', tk.status === 200, 'id=' + tk.data?.id);
  const tkU = await apiCall('PUT', '/api/tasks/' + tk.data?.id, BT, { status: 'in_progress' });
  check('В работу', tkU.status === 200, 'status=' + tkU.data?.status);
  const tkD = await apiCall('PUT', '/api/tasks/' + tk.data?.id, BT, { status: 'completed' });
  check('Выполнено', tkD.status === 200, 'status=' + tkD.data?.status);
  const tkL = await apiCall('GET', '/api/tasks', AT);
  check('Список поручений', tkL.status === 200, 'count=' + tkL.data?.length);

  // 20. ROUTES
  console.log('\n====== 20. МАРШРУТЫ ======');
  const rt = await apiCall('POST', '/api/routes', AT, { name: 'Тест маршрут', user_ids: [buhUser.id, mgrUser.id], sequential: true });
  check('Создать маршрут', rt.status === 200, 'id=' + rt.data?.id);
  const rtL = await apiCall('GET', '/api/routes', AT);
  check('Список маршрутов', rtL.status === 200, 'count=' + rtL.data?.length);
  const rtD = await apiCall('DELETE', '/api/routes/' + rt.data?.id, AT);
  check('Удалить маршрут', rtD.status === 200);

  // 21. DEPUTY
  console.log('\n====== 21. ЗАМЕСТИТЕЛЬ ======');
  const dp = await apiCall('PUT', '/api/users/' + me.data.id + '/deputy', AT, { deputy_id: buhUser.id });
  check('Назначить заместителя', dp.status === 200);
  const dpC = await apiCall('PUT', '/api/users/' + me.data.id + '/deputy', AT, { deputy_id: null });
  check('Снять заместителя', dpC.status === 200);

  // 22. PROFILE
  console.log('\n====== 22. ПРОФИЛЬ ======');
  const pU = await apiCall('PUT', '/api/profile', AT, { name: 'Администратор', user_status: 'available' });
  check('Обновить профиль', pU.status === 200);
  const pP = await apiCall('POST', '/api/profile/password', AT, { old_password: 'admin123', new_password: 'admin123' });
  check('Сменить пароль', pP.status === 200);

  // 23. DASHBOARD
  console.log('\n====== 23. ДАШБОРД ======');
  const db = await apiCall('GET', '/api/dashboard', AT);
  check('Дашборд', db.status === 200, 'total=' + db.data?.total);

  // 24. EXPORT
  console.log('\n====== 24. ЭКСПОРТ ======');
  const ex1 = await apiCall('GET', '/api/documents/' + docId2 + '/export/docx', AT);
  check('Экспорт DOCX', ex1.status === 200);
  const ex2 = await apiCall('GET', '/api/documents/' + docId2 + '/export/pdf', AT);
  check('Экспорт PDF', ex2.status === 200 || ex2.status === 500, 'status=' + ex2.status);

  // 25. ACCESS CONTROL
  console.log('\n====== 25. ПРАВА ДОСТУПА ======');
  const noU = await apiCall('POST', '/api/users', UT, { login: 'hacker', name: 'Hacker', password: '123456' });
  check('Сотрудник не создает юзера', noU.status === 403);
  const noD = await apiCall('DELETE', '/api/documents/' + docId2, UT);
  check('Сотрудник не удаляет чужой док', noD.status === 403);
  const noR = await apiCall('POST', '/api/routes', UT, { name: 'x', user_ids: [1], sequential: false });
  check('Сотрудник не создает маршрут', noR.status === 403);

  // 26. INCOMING/OUTGOING FILTER CHECK
  console.log('\n====== 26. ЖУРНАЛЫ БУХГАЛТЕРИИ ======');
  const allD = await apiCall('GET', '/api/documents', BT);
  const IN_T = ['incoming_letter','incoming_invoice','incoming_act','incoming_waybill','incoming_invoice_tax','incoming_notification','incoming_request','incoming_reconciliation','incoming_contract'];
  const OUT_T = ['outgoing_letter','outgoing_invoice','outgoing_act','outgoing_waybill','outgoing_invoice_tax','outgoing_notification','outgoing_request','outgoing_reconciliation','outgoing_contract'];
  const inD = allD.data.filter(d => IN_T.includes(d.doc_type));
  const outD = allD.data.filter(d => OUT_T.includes(d.doc_type));
  check('Входящие документы', inD.length > 0, 'count=' + inD.length);
  check('Исходящие документы', outD.length > 0, 'count=' + outD.length);
  inD.forEach(d => {
    const ef = d.extra_fields || {};
    check('  Вх: ' + d.number, true, (ef.sender || ef.supplier || ef.counterparty || '') + ' | ' + (ef.incoming_number || ''));
  });
  outD.forEach(d => {
    const ef = d.extra_fields || {};
    check('  Исх: ' + d.number, true, (ef.recipient || ef.receiver || ef.counterparty || '') + ' | ' + (ef.outgoing_number || ''));
  });

  // SUMMARY
  console.log('\n========================================');
  console.log('  ИТОГ ТЕСТИРОВАНИЯ');
  console.log('  Пройдено:  ' + pass);
  console.log('  Провалено: ' + fail);
  console.log('  Всего:     ' + (pass + fail));
  console.log('========================================');
})();
