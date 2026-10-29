"""Register selected local NASA test engines into an existing organization."""
import argparse
import json
from pathlib import Path
from uuid import UUID
from sentinel.config import ROOT,load_database_url
from sentinel.db import Database
from .replay import register_replay


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['register-replay'])
    p.add_argument('--tenant-id',type=UUID,required=True)
    p.add_argument('--actor-user-id',type=UUID,required=True,help='Existing authorized audit actor; CLI itself requires privileged DB access')
    p.add_argument('--subset',choices=['FD001','FD002','FD003','FD004'],required=True)
    p.add_argument('--engine-id',type=int,action='append',required=True)
    p.add_argument('--data-dir',type=Path,default=ROOT/'data/raw')
    p.add_argument('--env-file')
    a=p.parse_args(); database=None
    try:
        database=Database(load_database_url(a.env_file))
        if not database.ready(): raise ValueError()
        result=register_replay(database,a.tenant_id,a.actor_user_id,a.subset,a.engine_id,a.data_dir)
    except Exception:
        p.exit(1,'Replay registration failed: check migration, local dataset, selected IDs and authorized organization/actor. No credentials printed.\n')
    finally:
        if database: database.close()
    print(json.dumps(result,indent=2))
    if any(r['status']=='conflict' for r in result['results']): p.exit(2)

if __name__=='__main__': main()
