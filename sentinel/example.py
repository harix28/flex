"""Generate a real replay request from a locally downloaded test engine."""
import argparse
import json
from pathlib import Path
from .data import read_data, SUBSETS, SETTINGS, SENSORS


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--data-dir',type=Path,required=True)
    p.add_argument('--subset',choices=SUBSETS,required=True)
    p.add_argument('--engine',type=int,default=1)
    p.add_argument('--out',type=Path,default=Path('request.json'))
    a = p.parse_args()
    df = read_data(a.data_dir/f'test_{a.subset}.txt')
    g = df[df.engine_id == a.engine].tail(30)
    if g.empty:
        p.error('Unknown engine')
    payload = {'subset':a.subset,'engine_id':a.engine,'data_mode':'replay','observations':[
        {'cycle':int(row.cycle),'settings':row[SETTINGS].tolist(),'sensors':row[SENSORS].tolist()}
        for _,row in g.iterrows()]}
    a.out.write_text(json.dumps(payload,indent=2))
    print(a.out)


if __name__ == '__main__':
    main()
