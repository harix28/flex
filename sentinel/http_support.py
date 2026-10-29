"""Bounded requests and sanitized responses/logs shared by every route."""
import logging
from uuid import uuid4
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

logger = logging.getLogger('sentinel.http')
MAX_BODY_BYTES = 1024 * 1024
SAFE_CODES = {'authentication_required', 'model_not_loaded', 'nonconsecutive_cycles', 'invalid_history',
              'database_not_configured', 'database_unavailable', 'authentication_unavailable',
              'forbidden', 'https_required', 'csrf_failed', 'invalid_credentials', 'rate_limited',
              'conflict', 'last_admin', 'not_found', 'invalid_schema', 'replay_only', 'machine_archived',
              'idempotency_conflict', 'source_mismatch', 'source_version_conflict', 'observation_conflict', 'invalid_cycle_range',
              'version_conflict', 'outdated_evidence', 'assignee_ineligible', 'invalid_date_range'}


def error_response(request, status, code, message=None):
    error = {'code': code}
    if message:
        error['message'] = message
    return JSONResponse(status_code=status, content={
        'error': error, 'request_id': request.state.request_id})


def install_http_support(app):
    @app.middleware('http')
    async def bounds_and_trace(request, call_next):
        request.state.request_id = str(uuid4())
        try:
            body = bytearray()
            async for part in request.stream():
                if len(body) + len(part) > MAX_BODY_BYTES:
                    response = error_response(request, 413, 'payload_too_large')
                    break
                body.extend(part)
            else:
                request._body = bytes(body)
                response = await call_next(request)
        except Exception:
            # Exception messages, paths, query strings and payloads may contain secrets.
            response = error_response(request, 500, 'internal_error')
        response.headers['X-Request-ID'] = request.state.request_id
        response.headers['Cache-Control'] = 'no-store'
        logger.info('request_id=%s status=%s', request.state.request_id, response.status_code)
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid(request, exc):
        return error_response(request, 422, 'invalid_schema',
                              'Check request fields and required types.' if request.url.path.startswith(('/api/v1/auth/', '/api/v1/organizations/')) else
                              'Check cycles, 3 settings and 21 finite sensor readings per observation.')

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        code = exc.detail if isinstance(exc.detail, str) and exc.detail in SAFE_CODES else {
            404: 'not_found', 405: 'method_not_allowed'}.get(exc.status_code, 'http_error')
        response = error_response(request, exc.status_code, code)
        for header in ('Allow', 'Retry-After'):
            if exc.headers and header in exc.headers:
                response.headers[header] = exc.headers[header]
        return response
