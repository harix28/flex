"""Explicit registration of selected local test trajectories, never ingestion/prediction."""
from datetime import datetime,timezone
from uuid import uuid4
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from sentinel.data import SUBSETS,SENSORS,read_data,sha256
from sentinel.auth.permissions import permits
from sentinel.auth.service import lock_tenant
from .schemas import MachineCreate,SensorCreate,InstallationCreate
from .service import Registry


def register_replay(database,tenant,actor,subset,engine_ids,data_dir):
    if subset not in SUBSETS or not engine_ids or len(engine_ids)>20 or len(set(engine_ids))!=len(engine_ids) or any(type(i) is not int or i<1 or i>2147483647 for i in engine_ids):
        raise ValueError('Select a valid subset and 1 to 20 distinct positive engine IDs')
    path=data_dir/f'test_{subset}.txt'
    frame=read_data(path)  # Validates all columns, finite values, IDs and consecutive cycles.
    if not set(engine_ids)<=set(frame.engine_id.unique()):
        raise ValueError('Selected engine is absent from the local test partition')
    checksum=sha256(path)
    results=[]
    with database.transaction() as s:
        lock_tenant(s,tenant)
        roles=s.execute(text("""SELECT m.roles FROM memberships m JOIN users u ON u.id=m.user_id
          WHERE m.tenant_id=:t AND m.user_id=:u AND m.active AND u.active"""),dict(t=tenant,u=actor)).scalar_one_or_none()
        if not roles or not permits(roles,'registry.manage') or not permits(roles,'installations.manage'):
            raise ValueError('Active authorized organization membership required for selected audit actor')
        for engine in engine_ids:
            counts=dict(created=0,existing=0)
            try:
                with s.begin_nested():
                    registry=Registry(s,tenant,actor,uuid4())
                    code=f'NASA-{subset}-TEST-{engine}'
                    old=s.execute(text('SELECT * FROM machines WHERE tenant_id=:t AND asset_code=:code'),dict(t=tenant,code=code)).mappings().one_or_none()
                    if old:
                        if (old['data_source']!='nasa_replay' or old['source_subset']!=subset or old['source_engine_id']!=engine
                            or old['source_split']!='test' or old['lifecycle_status']=='archived'
                            or (old['source_file_sha256'] is not None and old['source_file_sha256']!=checksum)):
                            raise ValueError('Existing machine conflicts')
                        machine_id=old['id']; counts['existing']+=1
                    else:
                        machine_id=registry.create_machine(MachineCreate(asset_code=code,name=f'SIMULATED C-MAPSS {subset} test engine {engine}',
                          machine_type='cmapss_engine',data_source='nasa_replay',source_binding=dict(subset=subset,engine_id=engine,file_sha256=checksum)))['id']
                        counts['created']+=1
                    for channel in SENSORS:
                        sensor_code=f'{code}-{channel}'
                        sensor=s.execute(text('SELECT * FROM sensors WHERE tenant_id=:t AND sensor_code=:code'),dict(t=tenant,code=sensor_code)).mappings().one_or_none()
                        if sensor:
                            if sensor['data_source']!='nasa_replay' or sensor['channel_id']!=channel or sensor['retired']:
                                raise ValueError('Existing sensor conflicts')
                            sensor_id=sensor['id'];counts['existing']+=1
                        else:
                            sensor_id=registry.create_sensor(SensorCreate(sensor_code=sensor_code,name=f'Logical {channel}',kind='cmapss_channel',
                              data_source='nasa_replay',channel_id=channel))['id'];counts['created']+=1
                        installations=s.execute(text('SELECT * FROM installations WHERE tenant_id=:t AND sensor_id=:id'),dict(t=tenant,id=sensor_id)).mappings().all()
                        if installations:
                            if (len(installations)!=1 or installations[0]['machine_id']!=machine_id or
                                installations[0]['gateway_channel']!=channel or installations[0]['valid_to'] is not None):
                                raise ValueError('Existing installation conflicts')
                            counts['existing']+=1
                        else:
                            registry.install(machine_id,InstallationCreate(sensor_id=sensor_id,channel=channel,
                              installed_at=datetime.now(timezone.utc),note='Logical replay mapping; timestamp is registration time, not physical installation.'))
                            counts['created']+=1
                results.append(dict(engine_id=engine,status='registered',**counts))
            except (ValueError,IntegrityError,HTTPException):
                # A conflicting engine rolls back its entire savepoint, including audits.
                results.append(dict(engine_id=engine,status='conflict',created=0,existing=0))
    return dict(dataset='C-MAPSS',subset=subset,split='test',source_file_sha256=checksum,
                validation='local schema and engine presence; hash is provenance, not proof of official origin',results=results)
