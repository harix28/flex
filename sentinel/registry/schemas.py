from typing import Annotated, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, AwareDatetime, model_validator
from sentinel.data import SENSORS

Code = Annotated[str, Field(pattern=r'^[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}$')]
Label = Annotated[str, Field(min_length=1,max_length=120)]
Source = Literal['nasa_replay','physical_device']

class Input(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)

class Binding(Input):
    dataset: Literal['C-MAPSS'] = 'C-MAPSS'
    subset: Literal['FD001','FD002','FD003','FD004']
    engine_id: int = Field(strict=True,ge=1,le=2147483647)
    split: Literal['train','test'] = 'test'
    file_sha256: Annotated[str,Field(pattern=r'^[0-9a-f]{64}$')] | None = None

    @model_validator(mode='after')
    def new_partition_requires_version(self):
        if self.split=='train' and self.file_sha256 is None:
            raise ValueError('Training trajectories require an explicit source-file hash')
        return self

class MachineCreate(Input):
    asset_code: Code
    name: Label
    machine_type: Label
    manufacturer: Label | None = None
    model: Label | None = None
    serial_number: Label | None = None
    site: Label | None = None
    area: Label | None = None
    location: Label | None = None
    lifecycle_status: Literal['active','inactive'] = 'active'
    data_source: Source
    source_binding: Binding | None = None

    @model_validator(mode='after')
    def binding_matches_source(self):
        if (self.data_source=='nasa_replay') != (self.source_binding is not None):
            raise ValueError('Replay source binding required only for NASA replay')
        return self

class MachinePatch(Input):
    name: Label | None = None
    machine_type: Label | None = None
    manufacturer: Label | None = None
    model: Label | None = None
    serial_number: Label | None = None
    site: Label | None = None
    area: Label | None = None
    location: Label | None = None
    lifecycle_status: Literal['active','inactive'] | None = None

    @model_validator(mode='after')
    def required_fields_not_null(self):
        if not self.model_fields_set or any(k in self.model_fields_set and getattr(self,k) is None for k in ('name','machine_type','lifecycle_status')):
            raise ValueError('Supply nonempty valid patch fields')
        return self

class SensorCreate(Input):
    sensor_code: Code
    name: Label
    kind: Label
    unit: Label | None = None
    unit_reference: Annotated[str,Field(min_length=1,max_length=500)] | None = None
    data_source: Source
    channel_id: str | None = Field(default=None,max_length=32)
    hardware_device_id: Label | None = None
    status: Literal['active','retired'] = 'active'

    @model_validator(mode='after')
    def channel_matches_source(self):
        if self.data_source=='nasa_replay':
            if self.channel_id not in SENSORS or self.kind!='cmapss_channel' or any(v is not None for v in (self.unit,self.unit_reference,self.hardware_device_id)):
                raise ValueError('Replay sensor requires a logical sensor channel; physical metadata remains unknown')
        elif self.channel_id is not None:
            raise ValueError('Dataset channel IDs are reserved for replay')
        if self.unit is not None and (self.unit=='unknown' or not self.unit_reference):
            raise ValueError('Known unit requires an authoritative metadata reference')
        if self.unit is None and self.unit_reference is not None:
            raise ValueError('Unit reference requires a unit')
        return self

class SensorPatch(Input):
    name: Label | None = None
    kind: Label | None = None
    unit: Label | None = None
    unit_reference: Annotated[str,Field(min_length=1,max_length=500)] | None = None
    hardware_device_id: Label | None = None
    status: Literal['active','retired'] | None = None

    @model_validator(mode='after')
    def required_fields_not_null(self):
        if not self.model_fields_set or any(k in self.model_fields_set and getattr(self,k) is None for k in ('name','kind','status')):
            raise ValueError('Supply nonempty valid patch fields')
        return self

class InstallationCreate(Input):
    sensor_id: UUID
    channel: Code
    installed_at: AwareDatetime
    removed_at: AwareDatetime | None = None
    note: Annotated[str,Field(max_length=1000)] | None = None

    @model_validator(mode='after')
    def valid_range(self):
        if self.removed_at is not None and self.removed_at<=self.installed_at:
            raise ValueError('Removal must follow installation')
        return self

class InstallationRemove(Input):
    removed_at: AwareDatetime
