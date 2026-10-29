"""Local NASA file selection and authenticated HTTP import. No DB bypass."""
import hashlib
import io
from pathlib import Path
from urllib.parse import urlsplit
import httpx
from sentinel.data import read_data,SETTINGS,SENSORS,SUBSETS
from .schemas import Batch,MAX_BATCH,MAX_CYCLE
from .service import payload_digest


def origin_for(url,allow_local_http=False):
    parsed=urlsplit(url)
    if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('','/'):
        raise ValueError('Use a server origin without credentials, path, query or fragment')
    if not parsed.hostname or (parsed.scheme!='https' and not
        (allow_local_http and parsed.scheme=='http' and parsed.hostname in ('127.0.0.1','localhost','::1'))):
        raise ValueError('HTTPS required, or explicitly allow loopback HTTP')
    return url.rstrip('/')


def load_selection(data_dir,subset,partition,engine_id,start_cycle=1,end_cycle=MAX_CYCLE):
    if subset not in SUBSETS or partition not in ('train','test'):
        raise ValueError('Invalid dataset selection')
    if not 1<=engine_id<=MAX_CYCLE or not 1<=start_cycle<=end_cycle<=MAX_CYCLE:
        raise ValueError('Invalid engine or cycle range')
    # Fixed NASA filename. Parse the exact bytes hashed, never a RUL file.
    raw=(Path(data_dir)/f'{partition}_{subset}.txt').read_bytes()
    frame=read_data(io.BytesIO(raw))
    selected=frame[(frame.engine_id==engine_id)&frame.cycle.between(start_cycle,end_cycle)]
    if selected.empty: raise ValueError('Selection contains no observations')
    source=dict(dataset='C-MAPSS',subset=subset,partition=partition,engine_id=engine_id,
                file_sha256=hashlib.sha256(raw).hexdigest(),schema_version=1)
    rows=[dict(cycle=int(row.cycle),settings=[float(row[k]) for k in SETTINGS],
               sensors=[float(row[k]) for k in SENSORS]) for _,row in selected.iterrows()]
    # Validate all selected rows before any HTTP writes.
    for offset in range(0,len(rows),MAX_BATCH):
        Batch.model_validate(dict(source=source,observations=rows[offset:offset+MAX_BATCH]))
    return source,rows


def checked(response):
    if response.status_code!=200:
        raise ValueError(f'HTTP {response.status_code}; import stopped (no credentials logged)')
    return response.json()


def import_selection(client,tenant_id,machine_id,csrf,source,rows,batch_size=500):
    if not 1<=batch_size<=MAX_BATCH: raise ValueError('Batch size must be 1..500')
    base=f'/api/v1/organizations/{tenant_id}/machines/{machine_id}'
    machine=checked(client.get(base))['machine']
    binding=machine.get('source_binding') or {}
    expected=(source['dataset'],source['subset'],source['partition'],source['engine_id'])
    actual=tuple(binding.get(k) for k in ('dataset','subset','split','engine_id'))
    if machine['data_source']!='nasa_replay' or actual!=expected or binding.get('file_sha256') not in (None,source['file_sha256']):
        raise ValueError('Selected file/trajectory does not match registered machine')
    result=dict(inserted=0,existing=0,conflicting_batches=0,conflicting_observations=None,batches=[])
    for offset in range(0,len(rows),batch_size):
        payload=Batch.model_validate(dict(source=source,observations=rows[offset:offset+batch_size]))
        response=client.post(base+'/replay-batches',json=payload.model_dump(mode='json'),
                             headers={**csrf,'Idempotency-Key':'nasa-'+payload_digest(payload)})
        entry=dict(http_status=response.status_code)
        if response.status_code==409:
            result['conflicting_batches']+=1
            entry['error']=response.json().get('error',{}).get('code','conflict')
            result['batches'].append(entry)
            return result
        outcome=checked(response)
        batch=outcome['batch']
        replayed=outcome['idempotency_replayed']
        # Stored outcome is original. Retry itself inserts no observations.
        result['inserted']+=0 if replayed else batch['inserted_count']
        result['existing']+=batch['requested_count'] if replayed else batch['existing_count']
        entry.update(batch=batch,idempotency_replayed=replayed)
        result['batches'].append(entry)
    return result


def authenticated_import(origin,email,password,tenant_id,machine_id,source,rows,batch_size=500):
    with httpx.Client(base_url=origin,timeout=30,follow_redirects=False,trust_env=False) as client:
        auth=checked(client.post('/api/v1/auth/login',headers={'Origin':origin,'X-CSRF-Protection':'1'},
                                 json={'email':email,'password':password}))
        csrf={'Origin':origin,'X-CSRF-Token':auth['csrf_token']}
        try:
            return import_selection(client,tenant_id,machine_id,csrf,source,rows,batch_size)
        finally:
            checked(client.post('/api/v1/auth/logout',headers=csrf))
