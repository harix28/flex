"""Run one verified offline RUL experiment; does not register/deploy or read RUL labels."""
import argparse
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from sentinel.data import SUBSETS, read_data
from sentinel.rul_experiments import ExperimentPredictor


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bundle',type=Path,required=True)
    p.add_argument('--trusted-sha256',required=True)
    p.add_argument('--subset',choices=SUBSETS,required=True)
    p.add_argument('--engine',type=int,required=True)
    p.add_argument('--partition',choices=['train','test'],default='test')
    p.add_argument('--cutoff',type=int)
    p.add_argument('--data-dir',type=Path,default=ROOT/'data/raw')
    args=p.parse_args()
    if args.engine<1 or (args.cutoff is not None and args.cutoff<1): p.error('IDs/cycles must be positive')
    model=ExperimentPredictor(args.bundle,args.trusted_sha256)
    source=read_data(args.data_dir/f'{args.partition}_{args.subset}.txt')
    history=source[source.engine_id==args.engine]
    if args.cutoff is not None: history=history[history.cycle<=args.cutoff]
    if history.empty: p.error('No matching history')
    result=model.predict(args.subset,history.to_dict('records'))
    result.update(subset=args.subset,partition=args.partition,engine_id=args.engine,
                  observed_cutoff_cycle=int(history.cycle.iloc[-1]),units='cycles',
                  disclaimer='Offline replay experiment. Nominal interval coverage is not a failure probability or a per-engine guarantee.')
    print(json.dumps(result,indent=2,allow_nan=False))


if __name__=='__main__': main()
