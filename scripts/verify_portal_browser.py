"""Optional real-browser regression. Run with pytest and Playwright installed.
Uses the existing disposable PostgreSQL fixtures; never accesses demo records.
"""
import socket
import threading
import time
from dataclasses import replace
import pytest
import uvicorn
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from tests.test_postgres import db
from tests.test_auth_postgres import setup, login
from tests.test_predictions_postgres import pred_client, registered_machine, DEFAULT_SETTINGS
from sentinel.api import create_app
from sentinel.config import ROOT

pytestmark = pytest.mark.postgres


def test_portal_manager_assignment_tenant_switch_and_monitoring(setup):
    from playwright.sync_api import sync_playwright, expect
    with pred_client(setup) as client:
        headers = login(client, setup)
        machine = registered_machine(client, setup, headers)
        response = client.post('/api/v1/work-orders', headers=headers, json={
            'machine_id': machine['id'], 'title': 'Browser review work order',
            'description': 'Isolated browser verification', 'priority': 'high'})
        assert response.status_code == 200
        order = response.json()['work_order']
    with setup['database'].transaction() as s:
        s.execute(text('INSERT INTO memberships(tenant_id,user_id,roles) VALUES (:t,:u,:r)'),
                  {'t':setup['b'],'u':setup['users']['plant_manager'],'r':['plant_manager']})
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    origin = f'http://127.0.0.1:{sock.getsockname()[1]}'
    settings = replace(setup['settings'], auth_origins=(origin,),
                       model_dir=DEFAULT_SETTINGS.model_dir, bundle_sha256=DEFAULT_SETTINGS.bundle_sha256)
    app = create_app(settings=settings)
    app.mount('/', StaticFiles(directory=ROOT/'apps/web/dist', html=True), name='portal')
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', log_level='error'))
    thread = threading.Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 15
        while not server.started and time.monotonic() < deadline:
            time.sleep(.05)
        assert server.started
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel='msedge', headless=True)
            page = browser.new_page()
            statuses = []
            page.on('response', lambda r: statuses.append((r.url.split(origin)[-1], r.status)))
            page.goto(origin)
            page.locator('#login-email').fill('plant_manager@example.com')
            page.locator('#login-password').fill(setup['password'])
            page.locator('button[type=submit]').click()
            expect(page.get_by_label('Active Organization')).to_be_visible()
            page.get_by_label('Active Organization').select_option(str(setup['a']))
            page.goto(origin + '/#/work-orders/' + order['id'])
            expect(page.get_by_role('heading', name=order['work_order_number'], exact=True)).to_be_visible()
            page.get_by_role('button', name='Assign Tech', exact=True).click()
            page.get_by_label('Select Technician *').select_option(str(setup['users']['technician']))
            with page.expect_response(lambda r: r.url.endswith('/assignment')) as assignment:
                page.get_by_role('button', name='Confirm Assignment', exact=True).click()
            assert assignment.value.status == 200
            expect(page.get_by_role('button', name='Reassign Tech', exact=True)).to_be_visible()
            # Another session edits the order after the browser loaded it.
            with setup['database'].transaction() as s:
                s.execute(text('UPDATE work_orders SET version=version+1 WHERE id=:id'), {'id':order['id']})
            page.get_by_role('button', name='Reassign Tech', exact=True).click()
            with page.expect_response(lambda r: r.url.endswith('/assignment')) as conflict:
                page.get_by_role('button', name='Confirm Assignment', exact=True).click()
            assert conflict.value.status == 409
            expect(page.get_by_text('This record was modified', exact=False)).to_be_visible()
            page.get_by_role('button', name='Cancel', exact=True).click()
            page.get_by_label('Active Organization').select_option(str(setup['b']))
            expect(page.get_by_role('heading', name=order['work_order_number'], exact=True)).not_to_be_visible()
            page.wait_for_timeout(300)
            assert any(status == 404 and '/work-orders/' in path for path,status in statuses)
            page.goto(origin + '/#/model-monitoring')
            expect(page.get_by_role('heading', name='Model Governance & Monitoring', exact=False)).to_be_visible()
            expect(page.get_by_text('STATE: ACTIVE_UNTRACKED', exact=False)).to_be_visible()
            expect(page.get_by_text(DEFAULT_SETTINGS.bundle_sha256, exact=True)).to_be_visible()
            page.screenshot(path=str(ROOT/'.runtime/phase89-browser-monitoring.png'), full_page=True)
            print('Browser: manager login 200; eligible assignees 200; assignment 200; stale assignment 409; switched-tenant order 404; monitoring rendered')
            browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        sock.close()
