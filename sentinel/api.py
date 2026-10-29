"""Experimental inference and authenticated organization registry; not production-ready."""
import hmac
import logging
from contextlib import asynccontextmanager
from .db import Database
from .auth.api import auth_router
from .registry.api import registry_router
from .ingestion.api import ingestion_router
from .predictions.api import predictions_router
from .work_orders.api import work_orders_router
from .mlops.api import mlops_router
from .mlops.deployment import record_activation
from .config import Settings
from fastapi.middleware.cors import CORSMiddleware
from typing import Literal
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, FiniteFloat
from .config import ConfigurationError, load_settings, validate_api_key
from .http_support import install_http_support
from .data import COLUMNS
from .inference import Predictor


class Observation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    cycle: int = Field(strict=True, ge=1, le=2147483647)
    settings: list[FiniteFloat] = Field(min_length=3,max_length=3)
    sensors: list[FiniteFloat] = Field(min_length=21,max_length=21)


class PredictionRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    subset: Literal['FD001','FD002','FD003','FD004']
    engine_id: int = Field(strict=True,ge=1,le=2147483647)
    data_mode: Literal['replay']
    observations: list[Observation] = Field(min_length=1,max_length=1000)


def create_app(predictor=None, api_key=None, *, settings=None):
    # Explicit key/predictor injection keeps tests independent of local credentials.
    if settings is None and api_key is None:
        settings = load_settings()
    api_key = validate_api_key(api_key if api_key is not None else settings.api_key)
    if predictor is None and settings is not None and settings.model_dir is not None:
        try:
            predictor = Predictor(settings.model_dir, settings.bundle_sha256)
        except Exception:
            raise ConfigurationError('Model bundle rejected: check trusted manifest, artifact hashes, schema and file access') from None
    database = Database(settings.database_url) if settings and settings.database_url else None

    @asynccontextmanager
    async def lifespan(app):
        try:
            if database and predictor:
                try:
                    with database.transaction() as s:
                        record_activation(s, predictor)
                except Exception:
                    logging.getLogger('sentinel.mlops').error('Deployment activation could not be recorded')
            yield
        finally:
            if database:
                database.close()

    app = FastAPI(lifespan=lifespan,title='Meridian Sentinel — experimental ML backend',version='0.1.0',
                  description='Authenticated registry, persistent NASA replay observations, persistent RUL predictions, and maintenance work orders with human approval workflows. No physical ingestion or automated shutdown claims.',
                  docs_url='/docs',redoc_url=None)

    auth_settings = settings if settings is not None else Settings(api_key=api_key)
    if auth_settings.auth_origins:
        app.add_middleware(CORSMiddleware, allow_origins=list(auth_settings.auth_origins),
            allow_credentials=True, allow_methods=['GET','POST','PATCH','DELETE'],
            allow_headers=['Content-Type','X-CSRF-Token','X-CSRF-Protection','Idempotency-Key'])
    install_http_support(app)
    app.include_router(auth_router(database, auth_settings))
    app.include_router(registry_router(database, auth_settings))
    app.include_router(ingestion_router(database, auth_settings))
    app.include_router(predictions_router(database, auth_settings, predictor))
    app.include_router(work_orders_router(database, auth_settings))
    app.include_router(mlops_router(database, auth_settings, predictor))

    def authorized(x_api_key: str = Header(default='')):
        if not hmac.compare_digest(x_api_key.encode('utf-8'), api_key.encode('ascii')):
            raise HTTPException(401,'authentication_required')

    @app.get('/health')
    def health():
        return {'status':'ok','model_loaded':predictor is not None,'mode':'local_experiment'}

    @app.get('/health/database', responses={503: {'description': 'Database not ready'}})
    def database_ready():
        if database is None:
            raise HTTPException(503, 'database_not_configured')
        if not database.ready():
            raise HTTPException(503, 'database_unavailable')
        return {'status': 'ready'}

    @app.get('/health/live')
    def live():
        return {'status':'alive','mode':'local_experiment'}

    @app.get('/health/ready', responses={503: {'description': 'Model not loaded'}})
    def ready():
        if predictor is None:
            raise HTTPException(503, 'model_not_loaded')
        return {'status':'ready','model_loaded':True,'mode':'local_experiment'}

    @app.get('/health/deployment', responses={503: {'description': 'Model or database schema not ready'}})
    def deployment_ready():
        if predictor is None:
            raise HTTPException(503, 'model_not_loaded')
        if database is None or not database.ready():
            raise HTTPException(503, 'database_unavailable')
        return {'status': 'ready', 'model_loaded': True, 'database_ready': True}

    @app.get('/api/v1/experimental/model',dependencies=[Depends(authorized)])
    def model_report(request: Request):
        if predictor is None:
            raise HTTPException(503,'model_not_loaded')
        return {'bundle':predictor.meta,'evaluation':predictor.report,'request_id':request.state.request_id}

    @app.post('/api/v1/experimental/predict',dependencies=[Depends(authorized)])
    def predict(payload: PredictionRequest,request: Request):
        if predictor is None:
            raise HTTPException(503,'model_not_loaded')
        records = [dict(zip(COLUMNS,[payload.engine_id,o.cycle]+o.settings+o.sensors)) for o in payload.observations]
        # Unlike file import, online requests must already be chronological.
        cycles = [o.cycle for o in payload.observations]
        if any(b-a != 1 for a,b in zip(cycles,cycles[1:])):
            raise HTTPException(422,'nonconsecutive_cycles')
        try:
            result = predictor.predict(payload.subset,records)
        except ValueError:
            raise HTTPException(422,'invalid_history') from None
        return dict(result,engine_id=payload.engine_id,subset=payload.subset,request_id=request.state.request_id)

    return app
