"""Transactional, immutable replay input persistence. Never invokes inference."""
import hashlib
import json
import re
from fastapi import HTTPException
from sqlalchemy import text
from sentinel.data import SETTINGS,SENSORS
from .schemas import Batch,MAX_CYCLE,MAX_QUALITY_RANGE


def payload_digest(payload):
    return hashlib.sha256(json.dumps(payload.canonical(),sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def channel_schema():
    return dict(version=1,operating_settings=list(SETTINGS),sensor_channels=list(SENSORS))


def get_machine(s,tenant,machine,lock=False):
    row=s.execute(text('SELECT * FROM machines WHERE tenant_id=:t AND id=:m'+(' FOR UPDATE' if lock else '')),
                  dict(t=tenant,m=machine)).mappings().one_or_none()
    if row is None: raise HTTPException(404,'not_found')
    if row['data_source']!='nasa_replay': raise HTTPException(422,'replay_only')
    return row


def get_stream(s,tenant,machine):
    return s.execute(text('SELECT * FROM replay_streams WHERE tenant_id=:t AND machine_id=:m'),dict(t=tenant,m=machine)).mappings().one_or_none()


def batch_view(row):
    return {key:row[key] for key in ('id','tenant_id','machine_id','stream_id','actor_id','requested_count','inserted_count',
                                    'existing_count','first_cycle','last_cycle','ingested_at')}


def ingest(s,tenant,machine,actor,request_id,payload:Batch,key):
    if not re.fullmatch(r'[A-Za-z0-9._:-]{1,128}',key): raise HTTPException(422,'invalid_schema')
    asset=get_machine(s,tenant,machine,lock=True)
    fingerprint=payload_digest(payload)
    prior=s.execute(text("""SELECT * FROM replay_batches WHERE tenant_id=:t AND machine_id=:m
      AND operation='replay_ingest' AND idempotency_key=:key"""),dict(t=tenant,m=machine,key=key)).mappings().one_or_none()
    if prior:
        if prior['payload_sha256']!=fingerprint: raise HTTPException(409,'idempotency_conflict')
        return dict(batch=batch_view(prior),stream=dict(get_stream(s,tenant,machine)),idempotency_replayed=True)
    if asset['lifecycle_status']=='archived': raise HTTPException(409,'machine_archived')
    source=payload.source
    if (asset['source_dataset'],asset['source_subset'],asset['source_split'],asset['source_engine_id'])!=(source.dataset,source.subset,source.partition,source.engine_id):
        raise HTTPException(409,'source_mismatch')
    if asset['source_file_sha256'] is not None and asset['source_file_sha256']!=source.file_sha256:
        raise HTTPException(409,'source_version_conflict')
    if asset['source_file_sha256'] is None:
        s.execute(text('UPDATE machines SET source_file_sha256=:hash WHERE tenant_id=:t AND id=:m'),dict(hash=source.file_sha256,t=tenant,m=machine))
    stream=get_stream(s,tenant,machine)
    if stream is None:
        stream=s.execute(text("""INSERT INTO replay_streams(tenant_id,machine_id,dataset,subset,partition,engine_id,file_sha256,schema_version)
          VALUES (:t,:m,:dataset,:subset,:partition,:engine_id,:file_sha256,:schema_version) RETURNING *"""),
          dict(t=tenant,m=machine,**source.model_dump())).mappings().one()
    rows=sorted(payload.observations,key=lambda row:row.cycle)
    existing={row['cycle']:row for row in s.execute(text("""SELECT cycle,settings,sensors FROM replay_observations
      WHERE tenant_id=:t AND stream_id=:stream AND cycle=ANY(CAST(:cycles AS integer[]))"""),
      dict(t=tenant,stream=stream['id'],cycles=[row.cycle for row in rows])).mappings()}
    for row in rows:
        stored=existing.get(row.cycle)
        if stored and (stored['settings']!=row.settings or stored['sensors']!=row.sensors):
            raise HTTPException(409,'observation_conflict')
    additions=[row for row in rows if row.cycle not in existing]
    batch=s.execute(text("""INSERT INTO replay_batches(tenant_id,machine_id,stream_id,actor_id,request_id,idempotency_key,
      payload_sha256,requested_count,inserted_count,existing_count,first_cycle,last_cycle)
      VALUES (:t,:m,:stream,:actor,:request,:key,:hash,:requested,:inserted,:existing,:first,:last) RETURNING *"""),
      dict(t=tenant,m=machine,stream=stream['id'],actor=actor,request=request_id,key=key,hash=fingerprint,
           requested=len(rows),inserted=len(additions),existing=len(existing),first=rows[0].cycle,last=rows[-1].cycle)).mappings().one()
    if additions:
        s.execute(text("""INSERT INTO replay_observations(tenant_id,machine_id,stream_id,cycle,batch_id,settings,sensors,ingested_at)
          VALUES (:t,:m,:stream,:cycle,:batch,:settings,:sensors,:time)"""),
          [dict(t=tenant,m=machine,stream=stream['id'],cycle=row.cycle,batch=batch['id'],settings=row.settings,
                sensors=row.sensors,time=batch['ingested_at']) for row in additions])
    return dict(batch=batch_view(batch),stream=dict(stream),idempotency_replayed=False)


def history(s,tenant,machine,start,end,after,limit):
    get_machine(s,tenant,machine)
    if end<start: raise HTTPException(422,'invalid_cycle_range')
    stream=get_stream(s,tenant,machine)
    rows=s.execute(text("""SELECT stream_id,cycle,settings,sensors,observed_at,ingested_at,batch_id FROM replay_observations
      WHERE tenant_id=:t AND machine_id=:m AND cycle>=:start AND cycle<=:end AND cycle>:after
      ORDER BY cycle LIMIT :limit"""),dict(t=tenant,m=machine,start=start,end=end,after=after,limit=limit+1)).mappings().all()
    return dict(machine_id=machine,stream=dict(stream) if stream else None,channel_schema=channel_schema(),
                items=[dict(row) for row in rows[:limit]],next_after_cycle=rows[limit-1]['cycle'] if len(rows)>limit else None,
                data_mode='replay')


def quality(s,tenant,machine,start,end):
    get_machine(s,tenant,machine)
    stream=get_stream(s,tenant,machine)
    if end is None:
        latest=s.execute(text('SELECT max(cycle) FROM replay_observations WHERE tenant_id=:t AND machine_id=:m'),dict(t=tenant,m=machine)).scalar_one()
        end=min(MAX_CYCLE,start+999,max(start,latest or start))
    if end<start or end-start+1>MAX_QUALITY_RANGE: raise HTTPException(422,'invalid_cycle_range')
    rows=s.execute(text("""SELECT cycle,ingested_at FROM replay_observations WHERE tenant_id=:t AND machine_id=:m
      AND cycle>=:start AND cycle<=:end ORDER BY cycle"""),dict(t=tenant,m=machine,start=start,end=end)).mappings().all()
    gaps=[]; cursor=start
    for row in rows:
        if row['cycle']>cursor: gaps.append(dict(start_cycle=cursor,end_cycle=row['cycle']-1))
        cursor=row['cycle']+1
    if cursor<=end: gaps.append(dict(start_cycle=cursor,end_cycle=end))
    return dict(machine_id=machine,stream=dict(stream) if stream else None,data_mode='replay',
        requested_range=dict(start_cycle=start,end_cycle=end),observation_count=len(rows),
        first_cycle=rows[0]['cycle'] if rows else None,latest_cycle=rows[-1]['cycle'] if rows else None,
        missing_cycle_count=end-start+1-len(rows),gaps=gaps,is_contiguous=bool(rows) and not gaps,
        latest_ingested_at=max(row['ingested_at'] for row in rows) if rows else None,
        channel_schema=channel_schema(),schema_compatible=stream is not None and stream['schema_version']==1,
        observed_at_available=False)


def read_batch(s,tenant,batch_id):
    row=s.execute(text('SELECT * FROM replay_batches WHERE tenant_id=:t AND id=:id'),dict(t=tenant,id=batch_id)).mappings().one_or_none()
    if row is None: raise HTTPException(404,'not_found')
    get_machine(s,tenant,row['machine_id'])
    return dict(batch=batch_view(row),stream=dict(get_stream(s,tenant,row['machine_id'])))
