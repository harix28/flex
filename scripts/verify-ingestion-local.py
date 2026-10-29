"""Real Phase 5 ingestion and independent model HTTP verification on disposable PostgreSQL.
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
from sentinel.ingestion.importer import load_selection,authenticated_import


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
        source,rows=load_selection(ROOT/'data/raw','FD001','test',1)
        with httpx.Client(base_url=origin,timeout=30,trust_env=False) as client:
            login=expect('login',client.post('/api/v1/auth/login',headers={'Origin':origin,'X-CSRF-Protection':'1'},
              json={'email':'verify-admin-a@example.com','password':password}),200)
            csrf={'Origin':origin,'X-CSRF-Token':login.json()['csrf_token']}
            base=f'/api/v1/organizations/{first}'
            machine=expect('register_test_machine',client.post(base+'/machines',headers=csrf,json={
              'asset_code':'VERIFY-FD001-TEST-1','name':'SIMULATED verification engine 1','machine_type':'cmapss_engine',
              'data_source':'nasa_replay','source_binding':{'dataset':'C-MAPSS','subset':'FD001','split':'test','engine_id':1,
                                                        'file_sha256':source['file_sha256']}}),201).json()['machine']
            path=machine['detail_api_path']
            # The importer uses the existing registered machine, its own login and the same HTTP service as the CLI.
            imports=[authenticated_import(origin,'verify-admin-a@example.com',password,first,machine['id'],source,rows,10)
                     for _ in range(2)]
            assert (imports[0]['inserted'],imports[0]['existing'])==(31,0)
            assert (imports[1]['inserted'],imports[1]['existing'])==(0,31)
            history=expect('history',client.get(path+'/observations?limit=2'),200).json()
            quality=expect('quality',client.get(path+'/data-quality?start_cycle=1&end_cycle=31'),200).json()
            assert quality['observation_count']==31 and quality['gaps']==[]
            body={'source':source,'observations':[dict(rows[0],sensors=[999.0]+rows[0]['sensors'][1:])]}
            conflict=expect('conflict',client.post(path+'/replay-batches',headers={**csrf,'Idempotency-Key':'deliberate-conflict'},json=body),409).json()
            assert conflict['error']['code']=='observation_conflict'
            duplicate=expect('duplicate_new_key',client.post(path+'/replay-batches',headers={**csrf,'Idempotency-Key':'duplicate'},
              json={'source':source,'observations':rows}),200).json()
            assert duplicate['batch']['inserted_count']==0 and duplicate['batch']['existing_count']==31
            batch=expect('batch_detail',client.get(base+'/ingestion-batches/'+duplicate['batch']['id']),200).json()
            other=expect('other_tenant_login',client.post('/api/v1/auth/login',headers={'Origin':origin,'X-CSRF-Protection':'1'},
              json={'email':'verify-admin-b@example.com','password':password}),200)
            other_csrf={'Origin':origin,'X-CSRF-Token':other.json()['csrf_token']}
            expect('cross_tenant_history',client.get(path+'/observations'),404)
            expect('cross_tenant_ingest',client.post(path+'/replay-batches',headers={**other_csrf,'Idempotency-Key':'other'},
              json={'source':source,'observations':rows}),404)
            expect('forged_tenant_machine',client.get(path.replace(str(first),str(second))+'/observations'),404)
            prediction=expect('saved_model_replay',client.post('/api/v1/experimental/predict',headers={'X-API-Key':settings.api_key},
              json=json.loads((ROOT/'.runtime/replay-engine1.json').read_text())),200).json()
            assert abs(prediction['rul_cycles']-136.21971130371094)<.0001
        with database.transaction() as session:
            count=session.execute(text('SELECT count(*) FROM replay_observations')).scalar_one()
            assert count==31
        evidence=dict(transport='real HTTP loopback',database='disposable PostgreSQL 18',migration='0004_replay',
          source=source,http_statuses=results,imports=imports,history=history,quality=quality,conflict=conflict,
          duplicate=duplicate,stored_observations=count,prediction=prediction,model_verification=model_check,
          prediction_storage_implemented=False)
        (ROOT/'reports/phase5-http.json').write_text(json.dumps(evidence,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(dict(http_statuses=results,import_counts=[{k:r[k] for k in ('inserted','existing','conflicting_batches')} for r in imports],
                             stored_observations=count,saved_model_rul_cycles=prediction['rul_cycles']),indent=2))
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
