"""Send a local request.json to the running loopback backend."""
import argparse
import json
from pathlib import Path
import urllib.request
import urllib.error
from .config import ConfigurationError, load_settings


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--request',type=Path,default=Path('request.json'))
    p.add_argument('--port',type=int)
    a=p.parse_args()
    try:
        settings = load_settings(overrides={'SENTINEL_PORT': a.port})
        req=urllib.request.Request(f'http://127.0.0.1:{settings.port}/api/v1/experimental/predict',
            data=a.request.read_bytes(),headers={'Content-Type':'application/json','X-API-Key':settings.api_key})
        with urllib.request.urlopen(req,timeout=30) as r:
            print(f'HTTP {r.status}')
            print(json.dumps(json.load(r),indent=2))
    except urllib.error.HTTPError as exc:
        p.error(f'HTTP {exc.code}: check the shared key, readiness and replay request')
    except (urllib.error.URLError, OSError):
        p.error('Cannot read request or reach localhost; keep the server terminal open and check the port')
    except ConfigurationError as exc:
        p.error(str(exc))


if __name__=='__main__':
    main()
