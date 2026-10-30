import os
os.environ['OMP_NUM_THREADS']='2'
from pathlib import Path
import json,hashlib,pickletools,re,sys
import numpy as np
import pandas as pd
from sklearn.model_selection import GroupShuffleSplit
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import HistGradientBoostingRegressor
from sentinel.data import read_data,sha256
from sentinel.rul_experiments import ExperimentPredictor,windows,scores
root=Path.cwd();out=root/'reports/notebook12-comparison-20261029';out.mkdir(exist_ok=False)
nb=Path(r'C:\Users\HARI SHARMA\Downloads\12.ipynb')
def load(sub,part):
 d=read_data(root/'data/raw'/f'{part}_{sub}.txt')
 return d.rename(columns={'engine_id':'unit_id','cycle':'time_cycles',**{f'sensor_{i:02}':f'sensor_{i}' for i in range(1,22)}})
def partition(d):
 return next(GroupShuffleSplit(n_splits=1,test_size=.25,random_state=42).split(d,groups=d.unit_id))
sensors=[f'sensor_{i}' for i in range(1,22)]
d1=load('FD001','train');t1,_=partition(d1)
rolling=[c for c in sensors if d1.iloc[t1][c].std()>1e-5]
d=load('FD003','train');ti,vi=partition(d);tr=d.iloc[ti].copy();va=d.iloc[vi].copy()
active=[c for c in sensors if tr[c].std()>1e-5]
scaler=StandardScaler().fit(tr[active])
def features(d):
 x=pd.DataFrame(scaler.transform(d[active]),columns=active,index=d.index)
 tmp=x.copy();tmp['unit_id']=d.unit_id.values
 g=tmp.groupby('unit_id',sort=False)[rolling]
 blocks=[x,g.diff(5).fillna(0).add_suffix('_delta_5')]
 for w in [5,10,20]:
  blocks += [g.rolling(w,min_periods=1).mean().reset_index(level=0,drop=True).add_suffix(f'_mean_{w}'),g.rolling(w,min_periods=1).std().fillna(0).reset_index(level=0,drop=True).add_suffix(f'_std_{w}')]
 return pd.concat(blocks,axis=1).astype(np.float32)
x=features(tr);y=(tr.groupby('unit_id').time_cycles.transform('max')-tr.time_cycles).clip(upper=125)
# Static metadata check only, never pickle.load/joblib.load.
def static_names(name):
 b=(nb.parent/name).read_bytes()
 return [a for op,a,pos in pickletools.genops(b) if isinstance(a,str) and re.fullmatch(r'sensor_\d+(?:_.*)?',a)]
assert list(x.columns)==static_names('best_cmapss_model.pkl')
assert active==static_names('cmapss_scaler.pkl')
# Causality check: full and truncated history produce identical features at cutoff.
one=tr[tr.unit_id==tr.unit_id.iloc[0]]
np.testing.assert_allclose(features(one).iloc[29],features(one.iloc[:30]).iloc[-1])
model=HistGradientBoostingRegressor(max_iter=250,learning_rate=.05,max_leaf_nodes=31,random_state=42)
model.fit(x,y)
print('Reproduced FD003 model fit; feature contract matches static artifact metadata.',flush=True)
test=load('FD003','test');ft=features(test);last=test.groupby('unit_id').tail(1).sort_values('unit_id');pred=np.clip(model.predict(ft.loc[last.index]),0,125)
truth=np.loadtxt(root/'data/raw/RUL_FD003.txt');assert list(last.unit_id)==list(range(1,101))
ref=root/'runs/rul-improvement-20261027/FD003';meta=json.loads((ref/'results.json').read_text())
baseline=ExperimentPredictor(ref,meta['experiment_manifest_sha256'])
raw=read_data(root/'data/raw/test_FD003.txt');bx,_,ids,cycles=windows(raw,60,baseline.transform,'last');bp=baseline.model.predict(bx)
p=pred[ids-1];t=truth[ids-1]
result={'kind':'notebook_recipe_reproduction_NOT_supplied_pickle_execution','subset':'FD003','features':len(x.columns),'train_engines':sorted(map(int,tr.unit_id.unique())),'validation_engines':sorted(map(int,va.unit_id.unique())),'best_iterations':int(model.n_iter_),'notebook_sha256':sha256(nb),'supplied_files':{name:sha256(nb.parent/name) for name in ['best_cmapss_model.pkl','cmapss_scaler.pkl']},'common_uncapped':{'existing':scores(t,bp,ids),'notebook_reproduction':scores(t,p,ids)},'common_capped':{'existing':scores(np.minimum(t,125),bp,ids),'notebook_reproduction':scores(np.minimum(t,125),p,ids)},'all100_reproduction_uncapped':scores(truth,pred,last.unit_id.to_numpy()),'all100_reproduction_capped':scores(np.minimum(truth,125),pred,last.unit_id.to_numpy()),'caveats':['Not exact supplied binary verification; pickle files not loaded.','Notebook 75/25 split differs from baseline 70/15/reserved split.','Benchmark previously inspected; descriptive comparison, no fresh blind claim.','HGB auto early stopping uses internal row split, not engine grouping.','Notebook FD002/4 fit test-set normalization independently; invalid for a fixed train-only preprocessing deployment.','Rolling function in FD003 depends on FD001 ACTIVE_SENSORS global; reproduced intentionally.'],'protected_original_model_sha256':sha256(ref/'model.json')}
(out/'results.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
pd.DataFrame({'engine_id':ids,'true_rul':t,'existing':bp,'notebook_reproduction':p}).to_csv(out/'common_predictions.csv',index=False)
print(json.dumps({k:result[k] for k in ['common_uncapped','common_capped','all100_reproduction_capped']},indent=2),flush=True)
