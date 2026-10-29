"""Tenant, transaction, immutable-history and concurrency tests on PostgreSQL."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4
import pytest
from sqlalchemy import text,inspect
from sqlalchemy.exc import DBAPIError
from alembic import command
from tests.test_postgres import db
from tests.test_auth_postgres import setup,client_for,login
from tests.test_registry import machine_payload
from tests.test_ingestion import payload
from sentinel.ingestion.importer import load_selection,import_selection
from sentinel.config import ROOT
from sentinel.data import SETTINGS,SENSORS

pytestmark=pytest.mark.postgres


def registered(c,setup,h,**changes):
    base=f"/api/v1/organizations/{setup['a']}"
    response=c.post(base+'/machines',headers=h,json=machine_payload('REPLAY','nasa_replay',**changes))
    assert response.status_code==201,response.text
    return response.json()['machine']['detail_api_path']


def post(c,path,h,body,key='test'):
    return c.post(path+'/replay-batches',headers={**h,'Idempotency-Key':key},json=body)


def test_real_format_roundtrip_idempotency_and_history(setup):
    source,rows=load_selection(ROOT/'data/raw','FD001','test',1)
    with client_for(setup) as c:
        h=login(c,setup);path=registered(c,setup,h)
        body=dict(source=source,observations=rows)
        first=post(c,path,h,body);assert first.status_code==200,first.text
        assert first.json()['batch']['inserted_count']==31
        retry=post(c,path,h,body)
        assert retry.json()['batch']==first.json()['batch'] and retry.json()['idempotency_replayed']
        duplicate=post(c,path,h,body,'another')
        assert duplicate.json()['batch']['inserted_count']==0 and duplicate.json()['batch']['existing_count']==31
        history=c.get(path+'/observations?limit=2').json()
        assert history['channel_schema']['operating_settings']==SETTINGS
        assert history['channel_schema']['sensor_channels']==SENSORS
        assert history['next_after_cycle']==2
        for actual,expected in zip(history['items'],rows):
            assert actual['settings']==expected['settings'] and actual['sensors']==expected['sensors']
            assert actual['observed_at'] is None and actual['ingested_at'].endswith('+00:00')
        assert c.get(path+'/observations?after_cycle=2&limit=2').json()['items'][0]['cycle']==3
        assert c.get(path+'/observations?start_cycle=31&end_cycle=31&limit=1').json()['next_after_cycle'] is None
        assert c.get(path+'/observations?after_cycle=31').json()['items']==[]
        for suffix in ('?limit=0','?limit=501','?start_cycle=4&end_cycle=2'):
            assert c.get(path+'/observations'+suffix).status_code==422
        quality=c.get(path+'/data-quality').json()
        assert quality['observation_count']==31 and quality['gaps']==[] and quality['schema_compatible']
        bid=first.json()['batch']['id']
        assert c.get(f"/api/v1/organizations/{setup['a']}/ingestion-batches/{bid}").json()['batch']==first.json()['batch']
        assert c.get(path).json()['machine']['source_binding']['file_sha256']==source['file_sha256']
        assert set(x['name'] for x in inspect(setup['database'].engine).get_columns('replay_observations'))=={
            'tenant_id','machine_id','stream_id','cycle','batch_id','settings','sensors','observed_at','ingested_at'}


def test_out_of_order_gaps_conflicts_and_atomic_rollback(setup):
    with client_for(setup) as c:
        h=login(c,setup);path=registered(c,setup,h)
        assert post(c,path,h,payload((5,3))).status_code==200
        assert post(c,path,h,payload((1,)),'earlier').status_code==200
        q=c.get(path+'/data-quality?start_cycle=1&end_cycle=6').json()
        assert q['gaps']==[{'start_cycle':2,'end_cycle':2},{'start_cycle':4,'end_cycle':4},{'start_cycle':6,'end_cycle':6}]
        assert q['observation_count']==3 and q['missing_cycle_count']==3
        bad=payload((2,3));bad['observations'][1]['sensors'][0]=999
        r=post(c,path,h,bad,'conflict');assert r.status_code==409 and r.json()['error']['code']=='observation_conflict'
        assert post(c,path,h,payload((2,)),'test').status_code==409
        invalid=payload((2,4));invalid['observations'][1]['settings']=[1,2]
        assert post(c,path,h,invalid,'invalid').status_code==422
        assert [r['cycle'] for r in c.get(path+'/observations').json()['items']]==[1,3,5]
        with setup['database'].transaction() as s:
            assert s.execute(text('SELECT count(*) FROM replay_batches')).scalar_one()==2
        assert c.get(path+'/data-quality?start_cycle=1&end_cycle=10001').status_code==422


def test_source_identity_physical_and_request_bounds(setup):
    with client_for(setup) as c:
        h=login(c,setup);path=registered(c,setup,h)
        for field,value in [('partition','train'),('engine_id',2),('subset','FD002')]:
            body=payload();body['source'][field]=value
            assert post(c,path,h,body,field).status_code==409
        with setup['database'].transaction() as s:
            assert s.execute(text('SELECT count(*) FROM replay_streams')).scalar_one()==0
        assert post(c,path,h,payload()).status_code==200
        body=payload();body['source']['file_sha256']='b'*64
        assert post(c,path,h,body,'version').json()['error']['code']=='source_version_conflict'
        base=f"/api/v1/organizations/{setup['a']}"
        physical=c.post(base+'/machines',headers=h,json=machine_payload('PHYSICAL')).json()['machine']['detail_api_path']
        assert post(c,physical,h,payload()).status_code==422
        assert c.get(physical+'/observations').status_code==422
        for key in ('','x'*129,'bad key'):
            assert post(c,path,h,payload(),key).status_code==422
        assert c.post(path+'/replay-batches',headers=h,json=payload()).status_code==422
        assert c.post(path+'/replay-batches',headers={**h,'Idempotency-Key':'size','Content-Type':'application/json'},content=' '*1048577).status_code==413
        train=c.post(base+'/machines',headers=h,json=machine_payload('TRAIN','nasa_replay',source_binding={
            'subset':'FD001','engine_id':1,'split':'train','file_sha256':'b'*64}))
        assert train.status_code==201
        body['source']['partition']='train'
        assert post(c,train.json()['machine']['detail_api_path'],h,body).status_code==200


def test_roles_csrf_api_key_and_tenant_isolation(setup):
    with client_for(setup) as c:
        h=login(c,setup);path=registered(c,setup,h)
        assert post(c,path,{},payload()).status_code==403
        first=post(c,path,h,payload()).json()
        for role in ('viewer','technician','plant_manager'):
            h=login(c,setup,role+'@example.com')
            assert c.get(path+'/observations').status_code==200
            assert c.get(path+'/data-quality').status_code==200
            assert post(c,path,h,payload(),role).status_code==(200 if role=='plant_manager' else 403)
        h=login(c,setup,'admin-b@example.com')
        forged=path.replace(str(setup['a']),str(setup['b']))
        for target in (path,forged):
            assert c.get(target+'/observations').status_code==404
            assert post(c,target,h,payload(),'other').status_code==404
        assert c.get(f"/api/v1/organizations/{setup['b']}/ingestion-batches/{first['batch']['id']}").status_code==404
        c.cookies.clear()
        assert post(c,path,{'X-API-Key':setup['settings'].api_key},payload()).status_code==401


def test_concurrent_duplicate_conflicting_and_same_key_requests(setup):
    with client_for(setup) as c:
        h=login(c,setup);path=registered(c,setup,h)
        def pair(bodies,keys):
            barrier=Barrier(2)
            def run(i):
                barrier.wait()
                return post(c,path,h,bodies[i],keys[i])
            with ThreadPoolExecutor(max_workers=2) as pool: return list(pool.map(run,range(2)))
        results=pair([payload(),payload()],['one','two'])
        assert [r.status_code for r in results]==[200,200]
        assert sorted(r.json()['batch']['inserted_count'] for r in results)==[0,1]
        results=pair([payload((2,)),payload((2,))],['same','same'])
        assert [r.status_code for r in results]==[200,200]
        assert sorted(r.json()['idempotency_replayed'] for r in results)==[False,True]
        changed=payload((3,));changed['observations'][0]['sensors'][0]=999
        results=pair([payload((3,)),changed],['three','four'])
        assert sorted(r.status_code for r in results)==[200,409]
        assert len(c.get(path+'/observations').json()['items'])==3


def test_database_constraints_and_immutable_history(setup):
    with client_for(setup) as c:
        h=login(c,setup);path=registered(c,setup,h)
        assert post(c,path,h,payload()).status_code==200
    statements=[
        "UPDATE machines SET source_split='train' WHERE data_source='nasa_replay'",
        "UPDATE machines SET source_file_sha256=repeat('b',64) WHERE data_source='nasa_replay'",
        "UPDATE replay_observations SET sensors=ARRAY[1.0]",
        "DELETE FROM replay_batches", "DELETE FROM replay_streams",
        "INSERT INTO replay_observations SELECT tenant_id,machine_id,stream_id,cycle,batch_id,settings,sensors,observed_at,ingested_at FROM replay_observations",
        "INSERT INTO replay_observations SELECT tenant_id,machine_id,stream_id,2,batch_id,ARRAY[1.0],sensors,observed_at,ingested_at FROM replay_observations",
        "INSERT INTO replay_observations SELECT tenant_id,machine_id,stream_id,2,batch_id,ARRAY[1.0,'NaN'::float8,3.0],sensors,observed_at,ingested_at FROM replay_observations",
        "INSERT INTO replay_observations SELECT tenant_id,machine_id,stream_id,2,batch_id,ARRAY[1.0,'Infinity'::float8,3.0],sensors,observed_at,ingested_at FROM replay_observations",
        f"INSERT INTO replay_observations SELECT '{setup['b']}'::uuid,machine_id,stream_id,2,batch_id,settings,sensors,observed_at,ingested_at FROM replay_observations",
    ]
    for statement in statements:
        with pytest.raises(DBAPIError):
            with setup['database'].transaction() as s: s.execute(text(statement))


def test_upgrade_populated_phase4_binding(db):
    database,config=db
    command.downgrade(config,'0003_registry')
    from sentinel.auth.service import bootstrap
    from sentinel.registry.schemas import MachineCreate
    from sentinel.auth.security import new_token
    tenant,actor=bootstrap(database,'upgrade','Upgrade','upgrade@example.com',new_token(),'Upgrade')
    with database.transaction() as s:
        machine=s.execute(text("INSERT INTO machines(tenant_id,asset_code,name,machine_type,location,data_source,source_dataset,source_subset,source_split,source_engine_id) VALUES (:t,'OLD','Old','engine','unknown','nasa_replay','C-MAPSS','FD001','test',1) RETURNING id"),dict(t=tenant)).scalar_one()
    command.upgrade(config,'head')
    with database.transaction() as s:
        row=s.execute(text('SELECT * FROM machines WHERE id=:m'),dict(m=machine)).mappings().one()
        assert row['source_split']=='test' and row['source_file_sha256'] is None
    assert database.ready()
