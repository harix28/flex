"""Registry transactions reuse existing tables/repository and emit minimal audits."""
from fastapi import HTTPException
from sqlalchemy import select, text
from sentinel.db.repository import RegistryRepository
from .schemas import SensorCreate


def audit(s, action, tenant, actor, target_type, target, request_id):
    s.execute(text("""INSERT INTO auth_audit_events(action,tenant_id,actor_id,target_type,target_id,request_id)
      VALUES (:action,:tenant,:actor,:type,:target,:request)"""),
      dict(action=action,tenant=tenant,actor=actor,type=target_type,target=target,request=request_id))


def machine_view(row):
    result={k:row[k] for k in ('id','tenant_id','asset_code','name','machine_type','manufacturer','model','serial_number',
            'site','area','location','lifecycle_status','data_source','created_at','updated_at')}
    if result['location']=='unknown': result['location']=None
    result['source_binding']=dict(dataset=row['source_dataset'],subset=row['source_subset'],engine_id=row['source_engine_id'],split=row['source_split'],file_sha256=row['source_file_sha256']) if row['source_dataset'] else None
    result['source_label']={'nasa_replay':'Simulated dataset asset','physical_device':'Registered physical asset; connectivity unverified'}.get(row['data_source'],'Legacy source unclassified')
    result['health_status']='unknown'
    result['model_compatibility']='not_evaluated'
    result['detail_api_path']=f"/api/v1/organizations/{row['tenant_id']}/machines/{row['id']}"
    return result


def sensor_view(row):
    return {**{k:row[k] for k in ('id','tenant_id','sensor_code','name','kind','data_source','channel_id','hardware_device_id','unit_reference','created_at','updated_at')},
            'unit':None if row['canonical_unit']=='unknown' or row['data_source'] is None else row['canonical_unit'],
            'unit_metadata_status':'operator_supplied_reference' if row['unit_reference'] and row['data_source']=='physical_device' else 'unknown',
            'status':'retired' if row['retired'] else 'active',
            'identity_type':'logical_dataset_channel' if row['data_source']=='nasa_replay' else 'registered_sensor' if row['data_source']=='physical_device' else 'legacy_unclassified'}


def installation_view(row):
    return {**{k:row[k] for k in ('id','tenant_id','machine_id','sensor_id','note','created_at','updated_at')},
            'channel':row['gateway_channel'],'installed_at':row['valid_from'],'removed_at':row['valid_to']}

class Registry:
    def __init__(self,s,tenant,actor,request_id):
        self.s,self.tenant,self.actor,self.request_id=s,tenant,actor,request_id
        self.repo=RegistryRepository(s,tenant_id=tenant)

    def get(self,table,id,lock=False):
        t=self.repo._table(table)
        query=select(t).where(t.c.tenant_id==self.tenant,t.c.id==id)
        if lock: query=query.with_for_update()
        row=self.s.execute(query).mappings().one_or_none()
        if row is None: raise HTTPException(404,'not_found')
        return row

    def event(self,action,table,id):
        audit(self.s,action,self.tenant,self.actor,{'machines':'machine','sensors':'sensor','installations':'installation'}[table],id,self.request_id)

    def update(self,table,id,values):
        t=self.repo._table(table)
        self.s.execute(t.update().where(t.c.tenant_id==self.tenant,t.c.id==id).values(**values))
        return self.get(table,id)

    def create_machine(self,payload):
        values=payload.model_dump(exclude={'source_binding'})
        values['location']=values['location'] or 'unknown'
        binding=payload.source_binding
        if binding:
            values.update(source_dataset=binding.dataset,source_subset=binding.subset,source_engine_id=binding.engine_id,source_split=binding.split,source_file_sha256=binding.file_sha256)
        id=self.repo.add('machines',**values)
        self.event('machine_created','machines',id)
        return machine_view(self.get('machines',id))

    def patch_machine(self,id,payload):
        old=self.get('machines',id,True)
        if old['lifecycle_status']=='archived': raise HTTPException(409,'conflict')
        values=payload.model_dump(exclude_unset=True)
        if 'location' in values: values['location']=values['location'] or 'unknown'
        values['version']=old['version']+1
        row=self.update('machines',id,values)
        self.event('machine_updated','machines',id)
        return machine_view(row)

    def archive(self,id):
        row=self.get('machines',id,True)
        if row['lifecycle_status']!='archived':
            row=self.update('machines',id,dict(lifecycle_status='archived',version=row['version']+1))
            self.event('machine_archived','machines',id)
        return machine_view(row)

    def create_sensor(self,payload):
        values=payload.model_dump(exclude={'unit','status'})
        values.update(canonical_unit=payload.unit or 'unknown',retired=payload.status=='retired')
        id=self.repo.add('sensors',**values)
        self.event('sensor_created','sensors',id)
        return sensor_view(self.get('sensors',id))

    def patch_sensor(self,id,payload):
        row=self.get('sensors',id,True)
        if row['retired'] and payload.status=='active': raise HTTPException(409,'conflict')
        old=sensor_view(row)
        values={k:old[k] for k in SensorCreate.model_fields}
        values.update(payload.model_dump(exclude_unset=True))
        from pydantic import ValidationError
        try: validated=SensorCreate.model_validate(values)
        except ValidationError: raise HTTPException(422,'invalid_schema') from None
        changes=validated.model_dump(exclude={'sensor_code','data_source','channel_id','unit','status'})
        changes.update(canonical_unit=validated.unit or 'unknown',retired=validated.status=='retired')
        result=self.update('sensors',id,changes)
        self.event('sensor_updated','sensors',id)
        return sensor_view(result)

    def install(self,machine_id,payload):
        machine=self.get('machines',machine_id,True)
        sensor=self.get('sensors',payload.sensor_id,True)
        if (machine['lifecycle_status']=='archived' or sensor['retired'] or machine['data_source'] is None
            or machine['data_source']!=sensor['data_source']): raise HTTPException(409,'conflict')
        if sensor['data_source']=='nasa_replay' and sensor['channel_id']!=payload.channel:
            raise HTTPException(422,'invalid_schema')
        id=self.repo.add('installations',machine_id=machine_id,sensor_id=payload.sensor_id,
                         gateway_channel=payload.channel,valid_from=payload.installed_at,valid_to=payload.removed_at,note=payload.note)
        self.event('installation_created','installations',id)
        return installation_view(self.get('installations',id))

    def remove(self,id,payload):
        old=self.get('installations',id,True)
        if payload.removed_at<=old['valid_from']: raise HTTPException(422,'invalid_schema')
        if old['valid_to'] is not None:
            if old['valid_to']!=payload.removed_at: raise HTTPException(409,'conflict')
            return installation_view(old)
        row=self.update('installations',id,dict(valid_to=payload.removed_at))
        self.event('installation_removed','installations',id)
        return installation_view(row)
