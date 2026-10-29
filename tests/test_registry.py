"""Registry API and integrity tests against disposable real PostgreSQL databases."""
from datetime import datetime,timedelta,timezone
from uuid import uuid4
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from alembic import command
from tests.test_postgres import db,assets
from tests.test_auth_postgres import setup,client_for,login
from tests.test_api import KEY
from sentinel.registry.replay import register_replay
from sentinel.registry.schemas import MachineCreate,SensorCreate,InstallationCreate
from sentinel.registry.service import Registry
from sentinel.config import ROOT
from sentinel.data import SENSORS,SETTINGS

pytestmark=pytest.mark.postgres
START='2026-01-01T00:00:00Z'
END='2026-01-02T00:00:00Z'


def machine_payload(code='M1',source='physical_device',**changes):
    result=dict(asset_code=code,name='Registered test machine',machine_type='test-machine',data_source=source)
    if source=='nasa_replay': result['source_binding']=dict(subset='FD001',engine_id=1)
    return dict(result,**changes)


def sensor_payload(code='S1',source='physical_device',**changes):
    result=dict(sensor_code=code,name='Registered test sensor',kind='unknown',data_source=source)
    if source=='nasa_replay': result.update(kind='cmapss_channel',channel_id='sensor_01')
    return dict(result,**changes)


def create_pair(c,setup,headers,source='physical_device',code='1'):
    base=f"/api/v1/organizations/{setup['a']}"
    m=c.post(base+'/machines',headers=headers,json=machine_payload('M'+code,source))
    s=c.post(base+'/sensors',headers=headers,json=sensor_payload('S'+code,source))
    assert m.status_code==201,m.text
    assert s.status_code==201,s.text
    return base,m.json()['machine'],s.json()['sensor']


def install(c,base,m,s,headers,**changes):
    return c.post(f"{base}/machines/{m['id']}/installations",headers=headers,
      json=dict(dict(sensor_id=s['id'],channel='slot-1',installed_at=START),**changes))


def test_machine_sensor_create_read_update_archive_and_audits(setup):
    with client_for(setup) as c:
        h=login(c,setup);base,m,s=create_pair(c,setup,h)
        assert m['health_status']=='unknown' and m['model_compatibility']=='not_evaluated'
        assert m['location'] is None and m['source_binding'] is None
        assert m['detail_api_path']==f"{base}/machines/{m['id']}"
        assert s['unit'] is None
        assert c.get(m['detail_api_path']).json()['machine']['asset_code']=='M1'
        r=c.patch(m['detail_api_path'],headers=h,json={'name':'Changed','location':'Area A','lifecycle_status':'inactive'})
        assert r.status_code==200 and r.json()['machine']['name']=='Changed'
        assert r.json()['machine']['updated_at']>=m['updated_at']
        r=c.patch(f"{base}/sensors/{s['id']}",headers=h,json={'name':'Changed sensor','unit':'test-unit','unit_reference':'test-only authoritative fixture'})
        assert r.status_code==200 and r.json()['sensor']['unit']=='test-unit'
        assert c.post(m['detail_api_path']+'/archive',headers=h).json()['machine']['lifecycle_status']=='archived'
        assert c.patch(m['detail_api_path'],headers=h,json={'name':'Changed again'}).status_code==409
        assert c.delete(m['detail_api_path'],headers=h).status_code==405
        with setup['database'].transaction() as session:
            events=session.execute(text("SELECT action,actor_id,tenant_id,target_id FROM auth_audit_events WHERE target_id IS NOT NULL")).mappings().all()
            assert {e['action'] for e in events}=={'machine_created','sensor_created','machine_updated','sensor_updated','machine_archived'}
            assert all(e['actor_id']==setup['users']['admin'] and e['tenant_id']==setup['a'] for e in events)


def test_duplicate_codes_and_source_bindings_scoped_to_subset_and_tenant(setup):
    with client_for(setup) as c:
        h=login(c,setup);base,m,s=create_pair(c,setup,h,'nasa_replay')
        assert m['source_label']=='Simulated dataset asset'
        assert c.post(base+'/machines',headers=h,json=machine_payload('M1','physical_device')).status_code==409
        assert c.post(base+'/machines',headers=h,json=machine_payload('M2','nasa_replay')).status_code==409
        assert c.post(base+'/machines',headers=h,json=machine_payload('M3','nasa_replay',source_binding={'subset':'FD002','engine_id':1})).status_code==201
        assert c.post(base+'/sensors',headers=h,json=sensor_payload('S1')).status_code==409
        login(c,setup,'admin-b@example.com');h=login(c,setup,'admin-b@example.com')
        assert c.post(f"/api/v1/organizations/{setup['b']}/machines",headers=h,json=machine_payload('M1','nasa_replay')).status_code==201


@pytest.mark.parametrize('payload',[
    machine_payload(source='nasa_replay',source_binding=None),
    machine_payload(source_binding={'subset':'FD001','engine_id':1}),
    machine_payload(source='nasa_replay',source_binding={'subset':'FD005','engine_id':1}),
    machine_payload(source='nasa_replay',source_binding={'subset':'FD001','engine_id':0}),
    machine_payload(source='nasa_replay',source_binding={'subset':'FD001','engine_id':1,'split':'train'}),
    machine_payload(data_source='live'),machine_payload(tenant_id=str(uuid4())),
])
def test_invalid_machine_source_configuration(setup,payload):
    with client_for(setup) as c:
        h=login(c,setup)
        assert c.post(f"/api/v1/organizations/{setup['a']}/machines",headers=h,json=payload).status_code==422


def test_channel_definitions_unknown_metadata_and_sensor_validation(setup):
    with client_for(setup) as c:
        h=login(c,setup);base=f"/api/v1/organizations/{setup['a']}"
        catalog=c.get(base+'/registry/channels').json()
        assert [r['id'] for r in catalog['sensor_channels']]==SENSORS
        assert [r['id'] for r in catalog['operating_settings']]==SETTINGS
        assert all(r['unit'] is None and r['component'] is None and r['name'] is None for r in catalog['sensor_channels'])
        for changes in ({'channel_id':'setting_1'},{'channel_id':'sensor_22'},{'unit':'K','unit_reference':'unreviewed'}, {'hardware_device_id':'real-device'}):
            assert c.post(base+'/sensors',headers=h,json=sensor_payload(source='nasa_replay',**changes)).status_code==422
        assert c.post(base+'/sensors',headers=h,json=sensor_payload(unit='unit-without-reference')).status_code==422
        base,m,s=create_pair(c,setup,h,'nasa_replay')
        assert c.patch(f"{base}/sensors/{s['id']}",headers=h,json={'unit':'K','unit_reference':'unverified'}).status_code==422


@pytest.mark.parametrize('role,manage,installation',[('viewer',False,False),('technician',False,True),('plant_manager',True,True),('admin',True,True)])
def test_role_matrix_and_csrf(setup,role,manage,installation):
    with client_for(setup) as c:
        h=login(c,setup);base,m,s=create_pair(c,setup,h)
        h=login(c,setup,'admin-a@example.com' if role=='admin' else role+'@example.com')
        assert c.get(base+'/machines').status_code==200
        assert c.get(base+'/sensors').status_code==200
        assert c.post(base+'/machines',headers=h,json=machine_payload('M2')).status_code==(201 if manage else 403)
        assert c.patch(m['detail_api_path'],headers=h,json={'name':'Update'}).status_code==(200 if manage else 403)
        assert c.post(base+'/sensors',headers=h,json=sensor_payload('S2')).status_code==(201 if manage else 403)
        assert install(c,base,m,s,h).status_code==(201 if installation else 403)
        assert c.post(base+'/machines',json=machine_payload('M3')).status_code==403


def test_cross_tenant_reads_writes_archives_and_forged_references(setup):
    with client_for(setup) as c:
        h=login(c,setup);base,m,s=create_pair(c,setup,h)
        installed=install(c,base,m,s,h).json()['installation']
        h=login(c,setup,'admin-b@example.com');other=f"/api/v1/organizations/{setup['b']}"
        for resource,id in [('machines',m['id']),('sensors',s['id'])]:
            assert c.get(f'{other}/{resource}/{id}').status_code==404
            assert c.patch(f'{other}/{resource}/{id}',headers=h,json={'name':'Forged'}).status_code==404
            assert c.get(f'{base}/{resource}/{id}').status_code==404
        assert c.post(f"{other}/machines/{m['id']}/archive",headers=h).status_code==404
        assert c.get(f"{other}/machines/{m['id']}/installations").status_code==404
        assert c.post(f"{other}/installations/{installed['id']}/remove",headers=h,json={'removed_at':END}).status_code==404
        other_m=c.post(other+'/machines',headers=h,json=machine_payload('M1')).json()['machine']
        assert install(c,other,other_m,s,h).status_code==404
        assert c.get(other+'/sensors').json()['items']==[]


def test_identity_fields_and_source_cannot_be_mass_assigned(setup):
    with client_for(setup) as c:
        h=login(c,setup);base,m,s=create_pair(c,setup,h)
        for extra in ({'tenant_id':str(setup['b'])},{'asset_code':'NEW'},{'data_source':'nasa_replay'},{'source_binding':{'subset':'FD001','engine_id':1}},{'health_status':'healthy'}):
            assert c.patch(m['detail_api_path'],headers=h,json=extra).status_code==422
        assert c.patch(f"{base}/sensors/{s['id']}",headers=h,json={'sensor_code':'NEW'}).status_code==422


def test_replacement_history_removal_and_overlap_conflicts(setup):
    with client_for(setup) as c:
        h=login(c,setup);base,m,s=create_pair(c,setup,h)
        initial=install(c,base,m,s,h)
        assert initial.status_code==201
        row=initial.json()['installation']
        assert install(c,base,m,s,h,channel='different-slot').status_code==409
        replacement=c.post(base+'/sensors',headers=h,json=sensor_payload('S2')).json()['sensor']
        assert install(c,base,m,replacement,h).status_code==409
        assert c.post(f"{base}/installations/{row['id']}/remove",headers=h,json={'removed_at':START}).status_code==422
        remove=c.post(f"{base}/installations/{row['id']}/remove",headers=h,json={'removed_at':END})
        assert remove.status_code==200
        assert c.post(f"{base}/installations/{row['id']}/remove",headers=h,json={'removed_at':END}).status_code==200
        assert c.post(f"{base}/installations/{row['id']}/remove",headers=h,json={'removed_at':'2026-01-03T00:00:00Z'}).status_code==409
        assert install(c,base,m,replacement,h,installed_at=END).status_code==201
        history=c.get(m['detail_api_path']+'/installations').json()['items']
        assert len(history)==2 and history[0]['removed_at'] is not None and history[1]['removed_at'] is None
        assert len(c.get(m['detail_api_path']+'/installations?open_only=true').json()['items'])==1
        assert install(c,base,m,s,h,installed_at='2026-01-05T00:00:00').status_code==422


def test_archived_retired_and_source_mismatch_restrictions(setup):
    with client_for(setup) as c:
        h=login(c,setup);base,m,s=create_pair(c,setup,h)
        assert c.patch(f"{base}/sensors/{s['id']}",headers=h,json={'status':'retired'}).status_code==200
        assert install(c,base,m,s,h).status_code==409
        assert c.patch(f"{base}/sensors/{s['id']}",headers=h,json={'status':'active'}).status_code==409
        other=c.post(base+'/sensors',headers=h,json=sensor_payload('S2','nasa_replay')).json()['sensor']
        assert install(c,base,m,other,h,channel='sensor_01').status_code==409
        assert c.post(m['detail_api_path']+'/archive',headers=h).status_code==200
        active=c.post(base+'/sensors',headers=h,json=sensor_payload('S3')).json()['sensor']
        assert install(c,base,m,active,h).status_code==409


def test_pagination_filters_and_stable_code_order(setup):
    with client_for(setup) as c:
        h=login(c,setup);base=f"/api/v1/organizations/{setup['a']}"
        for code in ('C','A','B'):
            assert c.post(base+'/machines',headers=h,json=machine_payload(code,site='site-'+code)).status_code==201
        page1=c.get(base+'/machines?limit=2').json();page2=c.get(base+'/machines?limit=2&offset=2').json()
        assert [m['asset_code'] for m in page1['items']+page2['items']]==['A','B','C']
        assert page1['next_offset']==2 and page2['next_offset'] is None
        assert len(c.get(base+'/machines?site=site-A&data_source=physical_device').json()['items'])==1
        assert c.get(base+'/machines?asset_code=absent').json()['items']==[]
        for query in ('limit=0','limit=101','offset=-1','data_source=anything','lifecycle_status=healthy'):
            assert c.get(base+'/machines?'+query).status_code==422
        for code in ('C','A','B'):
            c.post(base+'/sensors',headers=h,json=sensor_payload(code))
        assert [s['sensor_code'] for s in c.get(base+'/sensors?limit=2').json()['items']]==['A','B']
        assert c.get(base+'/sensors?status=retired').json()['items']==[]


def test_registry_cannot_use_experimental_key_or_removed_membership(setup):
    with client_for(setup) as c:
        base=f"/api/v1/organizations/{setup['a']}"
        assert c.get(base+'/machines',headers={'X-API-Key':KEY}).status_code==401
        assert c.post(base+'/machines',headers={'X-API-Key':KEY},json=machine_payload()).status_code==401
        h=login(c,setup,'viewer@example.com')
        with setup['database'].transaction() as s:
            s.execute(text('UPDATE memberships SET active=false WHERE id=:id'),dict(id=setup['members']['viewer']))
        assert c.get(base+'/machines').status_code==404


def test_database_slot_concurrency_and_transaction_rollback(setup):
    database=setup['database'];t=setup['a'];u=setup['users']['admin']
    with database.transaction() as s:
        r=Registry(s,t,u,uuid4())
        m=r.create_machine(MachineCreate(**machine_payload()))
        sensors=[r.create_sensor(SensorCreate(**sensor_payload(code))) for code in ('S1','S2')]
    barrier=Barrier(2)
    def attempt(sensor):
        try:
            with database.transaction() as s:
                barrier.wait(timeout=5)
                s.execute(text("INSERT INTO installations(tenant_id,machine_id,sensor_id,gateway_channel,valid_from) VALUES (:t,:m,:s,'slot',:time)"),dict(t=t,m=m['id'],s=sensor['id'],time=datetime(2026,1,1,tzinfo=timezone.utc)))
            return 'created'
        except IntegrityError: return 'conflict'
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(attempt,sensors))==['conflict','created']
    with pytest.raises(IntegrityError):
        with database.transaction() as s:
            r=Registry(s,t,u,uuid4())
            r.create_machine(MachineCreate(**machine_payload('ROLLBACK')))
            r.create_machine(MachineCreate(**machine_payload('M1')))
    with database.transaction() as s:
        assert s.execute(text("SELECT count(*) FROM machines WHERE asset_code='ROLLBACK'")).scalar_one()==0
        assert s.execute(text("SELECT count(*) FROM auth_audit_events WHERE action='machine_created'")).scalar_one()==1


def test_direct_database_archival_retirement_and_null_source_constraints(setup):
    db=setup['database'];t=setup['a'];u=setup['users']['admin']
    with db.transaction() as s:
        r=Registry(s,t,u,uuid4());m=r.create_machine(MachineCreate(**machine_payload()));sensor=r.create_sensor(SensorCreate(**sensor_payload()))
        s.execute(text("UPDATE machines SET lifecycle_status='archived' WHERE id=:id"),dict(id=m['id']))
    with pytest.raises(IntegrityError):
        with db.transaction() as s:
            s.execute(text("INSERT INTO installations(tenant_id,machine_id,sensor_id,gateway_channel,valid_from) VALUES (:t,:m,:s,'slot',now())"),dict(t=t,m=m['id'],s=sensor['id']))
    for values in ({'source':'nasa_replay','subset':None},{'source':None,'subset':'FD001'}):
        with pytest.raises(IntegrityError):
            with db.transaction() as s:
                s.execute(text('UPDATE machines SET data_source=:source,source_subset=:subset WHERE id=:id'),dict(**values,id=m['id']))


def local_data(tmp_path):
    # Schema-valid local test fixture, explicitly not claimed to be official NASA data.
    p=tmp_path/'test_FD001.txt'
    p.write_text('\n'.join(' '.join(map(str,[engine,cycle]+[1.0]*24)) for engine in (1,2) for cycle in (1,2)))
    return tmp_path


def test_replay_registration_idempotency_explicit_engines_and_conflicts(setup,tmp_path):
    data=local_data(tmp_path);db=setup['database'];t=setup['a'];u=setup['users']['admin']
    first=register_replay(db,t,u,'FD001',[1],data)
    second=register_replay(db,t,u,'FD001',[1],data)
    assert first['results']==[dict(engine_id=1,status='registered',created=43,existing=0)]
    assert second['results']==[dict(engine_id=1,status='registered',created=0,existing=43)]
    with db.transaction() as s:
        assert s.execute(text('SELECT count(*) FROM machines')).scalar_one()==1
        assert s.execute(text('SELECT count(*) FROM sensors')).scalar_one()==21
        assert s.execute(text('SELECT count(*) FROM installations')).scalar_one()==21
        s.execute(text("UPDATE sensors SET retired=true WHERE channel_id='sensor_21'"))
    conflict=register_replay(db,t,u,'FD001',[1],data)
    assert conflict['results'][0]['status']=='conflict'
    for engines in ([99],[],[1,1]):
        with pytest.raises(ValueError):register_replay(db,t,u,'FD001',engines,data)
    with pytest.raises(ValueError):register_replay(db,t,setup['users']['viewer'],'FD001',[2],data)
    with pytest.raises(Exception):register_replay(db,uuid4(),u,'FD001',[2],data)


def test_registry_migration_preserves_legacy_and_adds_slot_constraint(db):
    database,config=db
    command.downgrade(config,'0002_auth')
    tid,machine,sensor=assets(database)
    command.upgrade(config,'head')
    with database.transaction() as s:
        row=s.execute(text('SELECT data_source,lifecycle_status,asset_code FROM machines WHERE id=:id'),dict(id=machine)).one()
        assert row.data_source is None and row.lifecycle_status=='inactive' and row.asset_code=='A'
        assert s.execute(text("SELECT count(*) FROM pg_constraint WHERE conname='installations_slot_no_overlap'")).scalar_one()==1


def test_cli_late_conflict_rolls_back_all_new_engine_records(setup,tmp_path):
    data=local_data(tmp_path);database=setup['database'];tenant=setup['a'];actor=setup['users']['admin']
    with database.transaction() as s:
        r=Registry(s,tenant,actor,uuid4())
        r.create_sensor(SensorCreate(**sensor_payload('NASA-FD001-TEST-1-sensor_21')))
    result=register_replay(database,tenant,actor,'FD001',[1],data)
    assert result['results'][0]['status']=='conflict'
    with database.transaction() as s:
        assert s.execute(text('SELECT count(*) FROM machines')).scalar_one()==0
        assert s.execute(text('SELECT count(*) FROM sensors')).scalar_one()==1
        assert s.execute(text('SELECT count(*) FROM installations')).scalar_one()==0
        assert s.execute(text("SELECT count(*) FROM auth_audit_events WHERE action='machine_created'")).scalar_one()==0


def test_database_rejects_retired_sensor_and_wrong_replay_slot(setup):
    database=setup['database'];tenant=setup['a'];actor=setup['users']['admin']
    with database.transaction() as s:
        r=Registry(s,tenant,actor,uuid4())
        m=r.create_machine(MachineCreate(**machine_payload(source='nasa_replay')))
        sensor=r.create_sensor(SensorCreate(**sensor_payload(source='nasa_replay')))
    def raw_install(slot):
        with database.transaction() as s:
            s.execute(text("INSERT INTO installations(tenant_id,machine_id,sensor_id,gateway_channel,valid_from) VALUES (:t,:m,:s,:slot,now())"),dict(t=tenant,m=m['id'],s=sensor['id'],slot=slot))
    with pytest.raises(IntegrityError): raw_install('sensor_02')
    with database.transaction() as s:
        s.execute(text('UPDATE sensors SET retired=true WHERE id=:id'),dict(id=sensor['id']))
    with pytest.raises(IntegrityError): raw_install('sensor_01')
