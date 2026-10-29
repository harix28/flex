"""Real registry and independent model HTTP verification on disposable PostgreSQL.
Requires explicit SENTINEL_TEST_ADMIN_URL; never resets an existing database.
Uses the existing trusted model/data and writes only sanitized evidence.
"""
import json
import subprocess
import os
from pathlib import Path
import socket
import sys
import threading
import time
from dataclasses import replace
from uuid import uuid4
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import httpx
import uvicorn
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sentinel.config import ROOT,load_settings,validate_database_url
from sentinel.check import verify_and_prepare
from sentinel.api import create_app
from sentinel.db import Database
from sentinel.auth.security import new_token
from sentinel.auth.service import bootstrap,create_user


def main():
    url=validate_database_url(os.environ.get('SENTINEL_TEST_ADMIN_URL',''))
    name='meridian_test_'+uuid4().hex
    admin=create_engine(url.set(database='postgres'),isolation_level='AUTOCOMMIT',hide_parameters=True,connect_args={'connect_timeout':3})
    database=None
    server=None
    thread=None
    sock=None
    created=False
    try:
        with admin.connect() as c:
            c.exec_driver_sql('CREATE DATABASE '+name)
            created=True
        raw=url.set(database=name).render_as_string(hide_password=False)
        config=Config(str(ROOT/'alembic.ini'))
        config.attributes['database_url']=raw
        command.upgrade(config,'head')
        database=Database(raw)
        password=new_token()
        first,admin_a=bootstrap(database,'verify-a','TEST Organization A','verify-admin-a@example.com',password,'TEST Admin A')
        second,admin_b=bootstrap(database,'verify-b','TEST Organization B','verify-admin-b@example.com',password,'TEST Admin B')
        with database.transaction() as s:
            for role in ('viewer','technician','plant_manager'):
                uid=create_user(s,'verify-'+role+'@example.com',password,'TEST '+role)
                s.execute(text('INSERT INTO memberships(tenant_id,user_id,roles) VALUES (:t,:u,:r)'),dict(t=first,u=uid,r=[role]))
        cli_command=[sys.executable,'-m','sentinel.registry','register-replay',
                     '--tenant-id',str(first),'--actor-user-id',str(admin_a),'--subset','FD001','--engine-id','2']
        cli_results=[]
        for _ in range(2):
            completed=subprocess.run(cli_command,env={**os.environ,'DATABASE_URL':raw},capture_output=True,text=True,timeout=60)
            if completed.returncode: raise RuntimeError('Registry CLI verification failed')
            cli_results.append(json.loads(completed.stdout))
        assert cli_results[0]['results'][0]['created']==43
        assert cli_results[1]['results'][0]['existing']==43
        sock=socket.socket()
        sock.bind(('127.0.0.1',0))
        port=sock.getsockname()[1]
        origin='http://127.0.0.1:'+str(port)
        settings=replace(load_settings(),database_url=raw,auth_enabled=True,auth_localhost=True,auth_origins=(origin,))
        model_check=verify_and_prepare(settings,ROOT/'data/raw',ROOT/'.runtime/replay-engine1.json')
        app=create_app(settings=settings)
        server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=port,proxy_headers=False,
                                            access_log=False,log_config=None,log_level='critical'))
        thread=threading.Thread(target=server.run,kwargs={'sockets':[sock]},daemon=True)
        thread.start()
        deadline=time.monotonic()+15
        while not server.started and thread.is_alive() and time.monotonic()<deadline:
            time.sleep(.05)
        if not server.started:
            raise RuntimeError('Verification HTTP server did not start')
        results={}
        def expect(label,response,status):
            results[label]=response.status_code
            if response.status_code!=status:
                raise RuntimeError('Unexpected HTTP status for '+label)
            return response
        headers={'Origin':origin,'X-CSRF-Protection':'1'}
        with httpx.Client(base_url=origin,timeout=10) as client:
            r=expect('admin_login',client.post('/api/v1/auth/login',headers=headers,
              json={'email':'verify-admin-a@example.com','password':password}),200)
            csrf={'Origin':origin,'X-CSRF-Token':r.json()['csrf_token']}
            old=client.cookies.get('meridian_session')
            expect('authenticated_me',client.get('/api/v1/auth/me'),200)
            expect('admin_member_list',client.get(f'/api/v1/organizations/{first}/members'),200)
            base=f'/api/v1/organizations/{first}'
            registration={'asset_code':'HTTP-FD001-TEST-1','name':'SIMULATED HTTP replay engine 1',
                          'machine_type':'cmapss_engine','data_source':'nasa_replay',
                          'source_binding':{'dataset':'C-MAPSS','subset':'FD001','engine_id':1,'split':'test'}}
            machine=expect('registry_machine_create',client.post(base+'/machines',headers=csrf,json=registration),201).json()['machine']
            channels=expect('registry_channels',client.get(base+'/registry/channels'),200).json()
            assert len(channels['sensor_channels'])==21 and len(channels['operating_settings'])==3
            sensor=expect('registry_sensor_create',client.post(base+'/sensors',headers=csrf,json={
              'sensor_code':'HTTP-S1','name':'Logical sensor_01','kind':'cmapss_channel','data_source':'nasa_replay','channel_id':'sensor_01'}),201).json()['sensor']
            mapping=expect('registry_installation_create',client.post(machine['detail_api_path']+'/installations',headers=csrf,json={
              'sensor_id':sensor['id'],'channel':'sensor_01','installed_at':'2026-01-01T00:00:00Z',
              'note':'Logical demo mapping; not physical installation'}),201).json()['installation']
            detail=expect('registry_machine_detail',client.get(machine['detail_api_path']),200).json()['machine']
            assert detail['health_status']=='unknown' and detail['source_label']=='Simulated dataset asset'
            expect('registry_installation_history',client.get(machine['detail_api_path']+'/installations'),200)
            expect('registry_duplicate',client.post(base+'/machines',headers=csrf,json=registration),409)
            expect('registry_remove_installation',client.post(base+'/installations/'+mapping['id']+'/remove',headers=csrf,
              json={'removed_at':'2026-01-02T00:00:00Z'}),200)
            registry_evidence={'machine_code':machine['asset_code'],'detail_api_path':machine['detail_api_path'],
              'source_label':detail['source_label'],'health_status':detail['health_status'],
              'sensor_channels':21,'operating_settings':3,'raw_telemetry_persisted':False}

            expect('cross_tenant_read',client.get(f'/api/v1/organizations/{second}/members'),404)
            expect('cross_tenant_write',client.post(f'/api/v1/organizations/{second}/members',headers=csrf,
              json={'user_id':str(admin_a),'roles':['admin']}),404)
            expect('missing_csrf',client.post('/api/v1/auth/logout'),403)
            expect('logout',client.post('/api/v1/auth/logout',headers=csrf),200)
            client.cookies.set('meridian_session',old,domain='127.0.0.1',path='/')
            expect('revoked_session',client.get('/api/v1/auth/me'),401)
            r=expect('viewer_login',client.post('/api/v1/auth/login',headers=headers,
              json={'email':'verify-viewer@example.com','password':password}),200)
            csrf={'Origin':origin,'X-CSRF-Token':r.json()['csrf_token']}
            expect('viewer_organization_read',client.get(f'/api/v1/organizations/{first}'),200)
            expect('viewer_member_list_denied',client.get(f'/api/v1/organizations/{first}/members'),403)
            expect('viewer_role_write_denied',client.post(f'/api/v1/organizations/{first}/members',headers=csrf,
              json={'user_id':str(admin_b),'roles':['admin']}),403)
            expect('registry_viewer_write_denied',client.post(base+'/machines',headers=csrf,json={**registration,'asset_code':'FORBIDDEN'}),403)
            expect('other_organization_login',client.post('/api/v1/auth/login',headers=headers,
              json={'email':'verify-admin-b@example.com','password':password}),200)
            expect('registry_cross_tenant_read',client.get(machine['detail_api_path']),404)
            expect('registry_forged_machine_id',client.get(f"/api/v1/organizations/{second}/machines/{machine['id']}"),404)

            prediction=expect('saved_model_replay',client.post('/api/v1/experimental/predict',
              headers={'X-API-Key':settings.api_key},json=json.loads((ROOT/'.runtime/replay-engine1.json').read_text())),200).json()
            assert abs(prediction['rul_cycles']-136.21971130371094)<.0001
            for path in ('live','ready','database'):
                expect('health_'+path,client.get('/health/'+path),200)
        with database.transaction() as s:
            audits=dict(s.execute(text('SELECT action,count(*) FROM auth_audit_events GROUP BY action')).all())
        evidence={'transport':'real HTTP over loopback socket','database':'new disposable PostgreSQL database',
          'http_statuses':results,'audit_counts':audits,'model_verification':model_check,
          'prediction':prediction,'prediction_is_separate_from_registry':True,'registry':registry_evidence,
          'replay_cli_runs':cli_results,'secrets_in_report':False}
        (ROOT/'reports/phase4-http.json').write_text(json.dumps(evidence,indent=2)+'\n')
        print(json.dumps(evidence,indent=2))
    finally:
        if server:
            server.should_exit=True
        if thread:
            thread.join(timeout=15)
            if thread.is_alive():
                raise RuntimeError('HTTP server cleanup incomplete; inspect disposable test database')
        if sock:
            sock.close()
        if database:
            database.close()
        if created:
            with admin.connect() as c:
                c.exec_driver_sql('DROP DATABASE '+name)
        admin.dispose()


if __name__=='__main__':
    main()
