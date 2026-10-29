"""Explicit operator command; password is prompted, never a command argument."""
import argparse
import getpass
import json
from uuid import UUID
import httpx
from .importer import origin_for,load_selection,authenticated_import
from .schemas import MAX_CYCLE


def main():
    parser=argparse.ArgumentParser(description='Import local NASA observations through authenticated HTTP')
    parser.add_argument('--base-url',required=True)
    parser.add_argument('--allow-local-http',action='store_true')
    parser.add_argument('--email',required=True)
    parser.add_argument('--tenant-id',type=UUID,required=True)
    parser.add_argument('--machine-id',type=UUID,required=True)
    parser.add_argument('--data-dir',default='data/raw')
    parser.add_argument('--subset',choices=['FD001','FD002','FD003','FD004'],required=True)
    parser.add_argument('--partition',choices=['train','test'],required=True)
    parser.add_argument('--engine-id',type=int,required=True)
    parser.add_argument('--start-cycle',type=int,default=1)
    parser.add_argument('--end-cycle',type=int,default=MAX_CYCLE)
    parser.add_argument('--batch-size',type=int,default=500)
    args=parser.parse_args()
    try:
        origin=origin_for(args.base_url,args.allow_local_http)
        if not 1<=args.batch_size<=500: raise ValueError('Batch size must be 1..500')
        source,rows=load_selection(args.data_dir,args.subset,args.partition,args.engine_id,args.start_cycle,args.end_cycle)
        password=getpass.getpass('Password (not logged): ')
        result=authenticated_import(origin,args.email,password,args.tenant_id,args.machine_id,source,rows,args.batch_size)
        print(json.dumps(result,indent=2))
        return 2 if result['conflicting_batches'] else 0
    except (ValueError,OSError,httpx.HTTPError):
        print('Import failed: check selection, server availability, session permission and source binding. No credentials logged.')
        return 1


if __name__=='__main__':
    raise SystemExit(main())
