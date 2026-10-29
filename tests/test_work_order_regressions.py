"""Regression coverage for live execution permissions, evidence and versioned notes."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from datetime import datetime,timedelta,timezone
import pytest
from fastapi import HTTPException
from sqlalchemy import text
from tests.test_postgres import db
from tests.test_auth_postgres import setup,login
from tests.test_predictions_postgres import pred_client,registered_machine,ingest_observations
from sentinel.ingestion.importer import load_selection
from sentinel.config import ROOT
from sentinel.work_orders import service

pytestmark=pytest.mark.postgres


def transition(c,h,wo,action,**extra):
    return c.post(f"/api/v1/work-orders/{wo['id']}/transitions",headers=h,
                  json=dict(version=wo['version'],action=action,**extra))


def create_manual(c,h,machine,**extra):
    r=c.post('/api/v1/work-orders',headers=h,json=dict(machine_id=machine['id'],
        title='Regression work order',description='Test-only human concern',**extra))
    assert r.status_code==200,r.text
    return r.json()['work_order']


def prepared(c,setup,h,state='in_progress'):
    machine=registered_machine(c,setup,h)
    wo=create_manual(c,h,machine)
    r=transition(c,h,wo,'approve');assert r.status_code==200,r.text
    wo=r.json()['work_order']
    r=c.post(f"/api/v1/work-orders/{wo['id']}/assignment",headers=h,
             json=dict(version=wo['version'],technician_id=str(setup['users']['technician'])))
    assert r.status_code==200,r.text
    wo=r.json()['work_order']
    if state!='approved':
        r=transition(c,h,wo,'start');assert r.status_code==200,r.text
        wo=r.json()['work_order']
    if state=='blocked':
        r=transition(c,h,wo,'block',reason='Waiting for review');assert r.status_code==200,r.text
        wo=r.json()['work_order']
    return wo


@pytest.mark.parametrize('action,state',[('start','approved'),('block','in_progress'),('resume','blocked'),('complete','in_progress')])
@pytest.mark.parametrize('change,status',[('viewer',403),('membership',404),('disabled',401)])
def test_execution_revocation_is_immediate(setup,action,state,change,status):
    with pred_client(setup) as admin,pred_client(setup) as tech:
        ha=login(admin,setup);ht=login(tech,setup,'technician@example.com')
        wo=prepared(admin,setup,ha,state)
        before=admin.get(f"/api/v1/work-orders/{wo['id']}/history").json()
        with setup['database'].transaction() as s:
            params=dict(t=setup['a'],u=setup['users']['technician'])
            if change=='viewer':
                s.execute(text("UPDATE memberships SET roles=ARRAY['viewer']::text[] WHERE tenant_id=:t AND user_id=:u"),params)
            elif change=='membership':
                s.execute(text('UPDATE memberships SET active=false WHERE tenant_id=:t AND user_id=:u'),params)
            else:
                s.execute(text('UPDATE users SET active=false WHERE id=:u'),params)
        result=transition(tech,ht,wo,action,reason='Test blocking reason',completion_summary='Test completion')
        assert result.status_code==status,result.text
        after=admin.get(f"/api/v1/work-orders/{wo['id']}/history").json()
        assert after['work_order']['version']==wo['version']
        assert after['work_order']['status']==wo['status']
        assert after['transitions']==before['transitions']


def test_manager_must_reassign_ineligible_assignee_before_execution(setup):
    with pred_client(setup) as c:
        h=login(c,setup);wo=prepared(c,setup,h)
        with setup['database'].transaction() as s:
            s.execute(text('UPDATE users SET active=false WHERE id=:u'),dict(u=setup['users']['technician']))
            s.execute(text("UPDATE memberships SET roles=ARRAY['technician']::text[] WHERE tenant_id=:t AND user_id=:u"),
                      dict(t=setup['a'],u=setup['users']['viewer']))
        r=transition(c,h,wo,'complete',completion_summary='Test completion')
        assert r.status_code==409 and r.json()['error']['code']=='assignee_ineligible'
        r=c.post(f"/api/v1/work-orders/{wo['id']}/assignment",headers=h,
                 json=dict(version=wo['version'],technician_id=str(setup['users']['viewer']),reason='Reassign disabled member'))
        assert r.status_code==200,r.text
        wo=r.json()['work_order']
        assert transition(c,h,wo,'complete',completion_summary='Test completion').status_code==200
        history=c.get(f"/api/v1/work-orders/{wo['id']}/history").json()
        assert len(history['assignments'])==2
        assert history['assignments'][1]['previous_assignee_id']==str(setup['users']['technician'])


def test_stale_evidence_rejected_then_explicit_fresh_draft(setup):
    source,rows=load_selection(ROOT/'data/raw','FD001','test',1)
    with pred_client(setup) as c:
        h=login(c,setup);machine=registered_machine(c,setup,h);path=machine['detail_api_path']
        ingest_observations(c,path,h,rows[:30],source)
        pred=c.post(path+'/predictions',headers=h,json={'cutoff_cycle':30}).json()['prediction']
        r=c.post(f"/api/v1/predictions/{pred['id']}/work-order-draft",headers=h)
        assert r.status_code==200,r.text
        wo=r.json()['work_order'];evidence=wo['evidence']
        before=c.get(f"/api/v1/work-orders/{wo['id']}/history").json()
        ingest_observations(c,path,h,rows[30:],source,key='advance')
        r=transition(c,h,wo,'approve')
        assert r.status_code==409 and r.json()['error']['code']=='outdated_evidence'
        detail=c.get(f"/api/v1/work-orders/{wo['id']}/history").json()
        assert detail['work_order']['is_evidence_outdated']
        assert detail['work_order']['evidence']==evidence and detail['work_order']['version']==wo['version']
        assert detail['transitions']==before['transitions']
        assert transition(c,h,wo,'cancel',reason='Replace outdated evidence').status_code==200
        pred=c.post(path+'/predictions',headers=h,json={'cutoff_cycle':31}).json()['prediction']
        r=c.post(f"/api/v1/predictions/{pred['id']}/work-order-draft",headers=h)
        assert r.status_code==200,r.text
        new=r.json()['work_order']
        assert new['id']!=wo['id'] and new['evidence']['cutoff_cycle']==31
        assert transition(c,h,new,'approve').status_code==200


@pytest.mark.parametrize('scoped',[False,True])
def test_created_and_due_filters_boundaries_and_pagination(setup,scoped):
    with pred_client(setup) as c:
        h=login(c,setup);machine=registered_machine(c,setup,h)
        a=create_manual(c,h,machine,due_date='2030-01-01')
        b=create_manual(c,h,machine,due_date='2030-02-01')
        create_manual(c,h,machine)
        base=f"/api/v1/organizations/{setup['a']}/work-orders" if scoped else '/api/v1/work-orders'
        params=dict(due_from='2030-01-01',due_to='2030-02-01',machine_id=machine['id'],status='draft',priority='medium')
        r=c.get(base,params=dict(params,limit=1));assert r.status_code==200,r.text
        assert r.json()['total']==2 and r.json()['items'][0]['id']==b['id']
        assert c.get(base,params=dict(params,limit=1,offset=1)).json()['items'][0]['id']==a['id']
        assert c.get(base,params=dict(params,offset=2)).json()['items']==[]
        stamp=datetime.fromisoformat(a['created_at']).astimezone(timezone(timedelta(hours=5,minutes=30))).isoformat()
        r=c.get(base,params=dict(created_from=stamp,created_to=stamp,due_from='2030-01-01',due_to='2030-01-01'))
        assert r.status_code==200 and [x['id'] for x in r.json()['items']]==[a['id']]
        for bad in (dict(due_from='2030-02-01',due_to='2030-01-01'),dict(created_from=b['created_at'],created_to=a['created_at']),
                    dict(created_from='2030-01-01T00:00:00'),dict(due_from='bad')):
            assert c.get(base,params=bad).status_code==422
        login(c,setup,'admin-b@example.com')
        r=c.get(base,params=params)
        assert r.status_code==404 if scoped else r.status_code==200 and r.json()['items']==[]


def test_notes_require_version_and_rollback_all_writes(setup,monkeypatch):
    with pred_client(setup) as c:
        h=login(c,setup);machine=registered_machine(c,setup,h);wo=create_manual(c,h,machine)
        base=f"/api/v1/work-orders/{wo['id']}"
        assert c.post(base+'/notes',headers=h,json={'note_text':'Missing version'}).status_code==422
        assert c.post(base+'/notes',headers=h,json={'version':True,'note_text':'Wrong type'}).status_code==422
        r=c.post(base+'/notes',headers=h,json={'version':2,'note_text':'Stale request'})
        assert r.status_code==409 and r.json()['error']['code']=='version_conflict'
        assert c.post(base+'/notes',headers=h,json={'version':1,'note_text':'<script>bad</script>'}).status_code==400
        def fail_audit(*args,**kwargs): raise HTTPException(503,'database_unavailable')
        with monkeypatch.context() as patch:
            patch.setattr(service,'record_audit',fail_audit)
            assert c.post(base+'/notes',headers=h,json={'version':1,'note_text':'Must roll back'}).status_code==503
        hist=c.get(base+'/history').json()
        assert hist['work_order']['version']==1 and hist['notes']==[]
        r=c.post(base+'/notes',headers=h,json={'version':1,'note_text':'Committed note'})
        assert r.status_code==200 and r.json()['work_order_version']==2
        assert c.patch(base,headers=h,json={'version':1,'title':'Stale edit'}).status_code==409
        hist=c.get(base+'/history').json()
        assert hist['work_order']['version']==2 and len(hist['notes'])==1
        with setup['database'].transaction() as s:
            count=s.execute(text("SELECT count(*) FROM auth_audit_events WHERE target_id=:id AND action='work_order_note_added'"),dict(id=wo['id'])).scalar_one()
            assert count==1


@pytest.mark.parametrize('other',['note','complete'])
def test_concurrent_note_and_mutation_commit_only_one(setup,other):
    with pred_client(setup) as c:
        h=login(c,setup);wo=prepared(c,setup,h);base=f"/api/v1/work-orders/{wo['id']}"
        barrier=Barrier(2)
        def run(index):
            barrier.wait()
            if index==1 and other=='complete':
                return transition(c,h,wo,'complete',completion_summary='Test completion')
            return c.post(base+'/notes',headers=h,json={'version':wo['version'],'note_text':f'Test note {index}'})
        with ThreadPoolExecutor(max_workers=2) as pool: responses=list(pool.map(run,range(2)))
        assert sorted(r.status_code for r in responses)==[200,409]
        hist=c.get(base+'/history').json()
        assert hist['work_order']['version']==wo['version']+1
        assert len(hist['notes'])==(0 if hist['work_order']['status']=='completed' else 1)


def test_replacement_prediction_at_same_cutoff_marks_evidence_outdated(setup):
    source,rows=load_selection(ROOT/'data/raw','FD001','test',1)
    with pred_client(setup) as c:
        h=login(c,setup);machine=registered_machine(c,setup,h);path=machine['detail_api_path']
        ingest_observations(c,path,h,rows,source)
        pred=c.post(path+'/predictions',headers=h,json={'cutoff_cycle':31}).json()['prediction']
        wo=c.post(f"/api/v1/predictions/{pred['id']}/work-order-draft",headers=h).json()['work_order']
        # Simulate a new bundle's stored result only inside this disposable DB.
        # No model files, original prediction, or input observations are modified.
        with setup['database'].transaction() as session:
            row=session.execute(text('SELECT * FROM predictions WHERE id=:id'),dict(id=pred['id'])).mappings().one()
            columns=[key for key in row if key not in ('id','created_at')]
            expressions=["repeat('b',64)" if key=='model_digest' else "'test-replacement'" if key=='model_version' else key for key in columns]
            session.execute(text('INSERT INTO predictions ('+','.join(columns)+') SELECT '+','.join(expressions)+' FROM predictions WHERE id=:id'),dict(id=pred['id']))
        current=c.get(f"/api/v1/work-orders/{wo['id']}").json()['work_order']
        assert current['latest_observation_cycle']==31 and current['is_evidence_outdated']
        assert current['evidence']==wo['evidence']
        r=transition(c,h,wo,'approve')
        assert r.status_code==409 and r.json()['error']['code']=='outdated_evidence'
