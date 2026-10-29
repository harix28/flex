"""Canonical replay arrays follow sentinel.data; no RUL or timestamp invention."""
from typing import Annotated,Literal
from pydantic import BaseModel,ConfigDict,Field,field_validator,model_validator
from sentinel.data import SETTINGS,SENSORS

MAX_CYCLE=2147483647
MAX_BATCH=500
MAX_QUALITY_RANGE=10000
FiniteNumber=Annotated[float,Field(strict=True,allow_inf_nan=False)]
Cycle=Annotated[int,Field(strict=True,ge=1,le=MAX_CYCLE)]
IdempotencyKey=Annotated[str,Field(pattern=r'^[A-Za-z0-9._:-]{1,128}$')]

class Input(BaseModel):
    model_config=ConfigDict(extra='forbid')

class Source(Input):
    dataset: Literal['C-MAPSS']='C-MAPSS'
    subset: Literal['FD001','FD002','FD003','FD004']
    partition: Literal['train','test']
    engine_id: Cycle
    file_sha256: Annotated[str,Field(pattern=r'^[0-9a-f]{64}$')]
    schema_version: Literal[1]=1

    @field_validator('schema_version',mode='before')
    @classmethod
    def strict_version(cls,value):
        if type(value) is not int: raise ValueError('Schema version must be integer')
        return value

class Observation(Input):
    cycle: Cycle
    settings: Annotated[list[FiniteNumber],Field(min_length=len(SETTINGS),max_length=len(SETTINGS))]
    sensors: Annotated[list[FiniteNumber],Field(min_length=len(SENSORS),max_length=len(SENSORS))]
    observed_at: None=None

    @field_validator('settings','sensors')
    @classmethod
    def normalize_signed_zero(cls,values):
        return [0.0 if value==0 else value for value in values]

class Batch(Input):
    source: Source
    observations: Annotated[list[Observation],Field(min_length=1,max_length=MAX_BATCH)]

    @model_validator(mode='after')
    def unique_cycles(self):
        if len({o.cycle for o in self.observations})!=len(self.observations):
            raise ValueError('Duplicate cycles within one batch')
        return self

    def canonical(self):
        value=self.model_dump(mode='json')
        value['observations'].sort(key=lambda row:row['cycle'])
        return value
