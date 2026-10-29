"""MLOps Operator CLI for model registration, validation, deployment, rollback, and monitoring."""
import argparse
import json
import os
import sys
from pathlib import Path
from uuid import UUID
from sentinel.config import load_database_url
from sentinel.db import Database
from sentinel.mlops.verification import verify_model_bundle
from sentinel.mlops.registry import register_model, list_models, get_model
from sentinel.mlops.deployment import (
    deploy_model, rollback_model, list_deployments, get_deployment_status, sync_release_pointer
)
from sentinel.mlops.drift import evaluate_input_drift
from sentinel.mlops.evaluation import evaluate_predictions_performance


def get_db():
    try:
        from sentinel.config import read_env, ROOT
        rt_env = ROOT / '.runtime' / 'postgres.env'
        if rt_env.exists() and 'DATABASE_URL' not in os.environ:
            os.environ.update(read_env(rt_env))
        db_url = load_database_url()
        return Database(db_url)
    except Exception as exc:
        sys.stderr.write(f"Database configuration error: {exc}\n")
        sys.exit(1)


def cmd_list_models(args):
    db = get_db()
    with db.transaction() as s:
        models = list_models(s, limit=args.limit, offset=args.offset)
    if not models:
        print("No models registered in the registry.")
        return
    print(f"{'VERSION':<16} {'FAMILY':<10} {'SUBSET':<8} {'WINDOW':<8} {'STATUS':<16} {'REGISTERED'}")
    print("-" * 75)
    for m in models:
        created = str(m['created_at'])[:19]
        print(f"{m['model_version']:<16} {m['model_family']:<10} {m['target_subset']:<8} {m['window_size']:<8} {m['review_status']:<16} {created}")


def cmd_register_model(args):
    db = get_db()
    model_dir = Path(args.model_dir).resolve()
    print(f"Verifying and registering bundle from: {model_dir}")
    with db.transaction() as s:
        try:
            reg = register_model(s, model_dir, args.trusted_sha256, args.actor, args.reason)
            print(f"[OK] Model '{reg['model_version']}' registered successfully.")
            print(f"     ID:             {reg['id']}")
            print(f"     Bundle SHA256:  {reg['bundle_digest']}")
            print(f"     Model SHA256:   {reg['model_digest']}")
            print(f"     Feature Schema: {reg['feature_schema']} ({reg['feature_count']} features)")
            print(f"     Review Status:  {reg['review_status']}")
        except Exception as exc:
            sys.stderr.write(f"Registration failed: {exc}\n")
            sys.exit(1)


def cmd_validate_candidate(args):
    model_dir = Path(args.model_dir).resolve()
    print(f"Validating model candidate bundle: {model_dir}")
    try:
        info = verify_model_bundle(model_dir, args.trusted_sha256)
        print("[OK] Candidate bundle passed all verification checks:")
        print(f"     Version:        {info['model_version']}")
        print(f"     Family:         {info['model_family']}")
        print(f"     Bundle SHA256:  {info['bundle_digest']}")
        print(f"     Model SHA256:   {info['model_digest']}")
        print(f"     Report SHA256:  {info['report_digest']}")
        print(f"     Feature Schema: {info['feature_schema']} ({info['feature_count']} features)")
        print(f"     Window Size:    {info['window_size']}")
        print(f"     Subset:         {info['target_subset']}")
    except Exception as exc:
        sys.stderr.write(f"Validation failed: {exc}\n")
        sys.exit(1)


def _configure_release(args, rollback=False):
    db = get_db()
    try:
        with db.transaction() as session:
            rel = (rollback_model if rollback else deploy_model)(
                session, args.target_version if rollback else args.model_version,
                args.actor, args.reason, Path(args.model_dir).resolve(), args.environment)
        print(f"[OK] Committed desired deployment: {rel['deployment_id']}")
        print('Restart using SENTINEL_RELEASE_POINTER to activate this release.')
    except Exception:
        sys.stderr.write('Release configuration failed. Check deployment status; if metadata committed, run sync-release-pointer before restart.\n')
        sys.exit(1)
    finally:
        db.close()


def cmd_deploy_model(args):
    _configure_release(args)


def cmd_rollback_model(args):
    _configure_release(args, rollback=True)


def cmd_sync_release_pointer(args):
    db = get_db()
    try:
        sync_release_pointer(db.engine)
        print('[OK] Release pointer synchronized from committed metadata.')
    finally:
        db.close()


def cmd_list_deployments(args):
    db = get_db()
    with db.transaction() as s:
        deps = list_deployments(s, limit=args.limit, offset=args.offset)
    if not deps:
        print("No deployment records found.")
        return
    print(f"{'VERSION':<16} {'ACTION':<10} {'STATUS':<12} {'ACTOR':<16} {'REASON':<25} {'CONFIGURED'}")
    print("-" * 95)
    for d in deps:
        created = str(d['created_at'])[:19]
        reason = d['reason'][:24]
        print(f"{d['model_version']:<16} {d['action']:<10} {d['status']:<12} {d['actor']:<16} {reason:<25} {created}")


def cmd_status(args):
    db = get_db()
    with db.transaction() as s:
        st = get_deployment_status(s)
    print(f"Overall Deployment State: {st['state']}")
    print(f"Running Model Version:    {st['running_model_version'] or 'Not loaded in active CLI context'}")
    if st['desired_deployment']:
        d = st['desired_deployment']
        print(f"Desired Release:          {d['model_version']} (action: {d['action']}, configured by: {d['actor']}, status: {d['status']})")
    elif st['active_deployment']:
        print(f"Desired Release:          {st['active_deployment']['model_version']} (active)")
    else:
        print("Desired Release:          None configured")
    if st['active_deployment']:
        a = st['active_deployment']
        print(f"Active Release:           {a['model_version']} (activated at: {a['activated_at']})")
    else:
        print("Active Release:           None activated")


def cmd_drift_monitoring(args):
    db = get_db()
    tenant_id = UUID(args.tenant_id)
    print(f"Running input drift monitoring for tenant: {tenant_id}")
    with db.transaction() as s:
        res = evaluate_input_drift(
            s,
            tenant_id=tenant_id,
            model_version=args.model_version,
            actor=args.actor,
            min_samples=args.min_samples,
            drift_threshold_z=args.drift_threshold
        )
    print(f"Status:       {res['status']}")
    print(f"Sample Count: {res.get('sample_count', 0)}")
    if res['status'] == 'insufficient_data':
        print(f"Message:      {res['metrics']['message']}")
    elif res['status'] == 'available':
        m = res['metrics']
        print(f"Drift Flag:   {'DRIFT DETECTED' if m['drift_detected'] else 'STABLE (No significant drift)'}")
        print(f"Drift Rate:   {m['drift_rate'] * 100:.1f}% ({m['drifted_varying_count']}/{m['total_varying_count']} channels)")
        if m['top_drifted_features']:
            print("\nTop Shifted Features:")
            for f in m['top_drifted_features']:
                print(f"  - {f['name']:<24}: z={f['statistic_value']} (ref mean: {f['ref_mean']}, curr mean: {f['curr_mean']})")
        print(f"\nDisclaimer:   {m['disclaimer']}")


def cmd_evaluate(args):
    db = get_db()
    tenant_id = UUID(args.tenant_id)
    labels_path = Path(args.labels_path).resolve()
    print(f"Running ground-truth evaluation for tenant: {tenant_id}")
    print(f"Labels source: {labels_path}")
    with db.transaction() as s:
        res = evaluate_predictions_performance(
            s,
            tenant_id=tenant_id,
            labels_path=labels_path,
            subset=args.subset,
            partition=args.partition,
            model_version=args.model_version,
            actor=args.actor,
            expected_labels_sha256=args.expected_sha256
        )
    print(f"Status:       {res['status']}")
    print(f"Sample Count: {res.get('sample_count', 0)}")
    if res['status'] == 'available':
        m = res['metrics']
        print(f"Protocol:     {m['evaluation_protocol']}")
        print(f"MAE:          {m['mae_cycles']} cycles")
        print(f"RMSE:         {m['rmse_cycles']} cycles")
        print(f"Mean Signed Error (Bias): {m['mean_signed_error_cycles']} cycles")
        print(f"Overestimation Rate:      {m['overestimation_frequency'] * 100:.1f}%")
        print(f"Mean Overestimation:      {m['mean_overestimation_cycles']} cycles")
        print(f"\nDisclaimer:   {m['disclaimer']}")
    else:
        print(f"Reason:       {res.get('reason')}")
        print(f"Message:      {res.get('metrics', {}).get('message')}")


def main():
    p = argparse.ArgumentParser(prog='python -m sentinel.mlops.cli', description='MLOps model registry, release and monitoring CLI')
    sub = p.add_subparsers(dest='command', required=True)

    # list-models
    p_lm = sub.add_parser('list-models', help='List registered models')
    p_lm.add_argument('--limit', type=int, default=50)
    p_lm.add_argument('--offset', type=int, default=0)
    p_lm.set_defaults(func=cmd_list_models)

    # register-model
    p_reg = sub.add_parser('register-model', help='Register a verified local model bundle')
    p_reg.add_argument('--model-dir', required=True, help='Path to directory containing bundle.json, model.json, report.json')
    p_reg.add_argument('--trusted-sha256', required=True, help='Expected 64-char lowercase SHA256 of bundle.json')
    p_reg.add_argument('--actor', default='operator:cli', help='Operator identity registering the model')
    p_reg.add_argument('--reason', default='Initial registration', help='Reason for registration')
    p_reg.set_defaults(func=cmd_register_model)

    # validate-candidate
    p_val = sub.add_parser('validate-candidate', help='Validate candidate bundle against contract')
    p_val.add_argument('--model-dir', required=True)
    p_val.add_argument('--trusted-sha256', default=None)
    p_val.set_defaults(func=cmd_validate_candidate)

    # deploy-model
    p_dep = sub.add_parser('deploy-model', help='Configure desired model release')
    p_dep.add_argument('--model-version', required=True)
    p_dep.add_argument('--actor', required=True)
    p_dep.add_argument('--reason', required=True)
    p_dep.add_argument('--model-dir', default='runs/fd001-v1')
    p_dep.add_argument('--environment', default='local')
    p_dep.set_defaults(func=cmd_deploy_model)

    # rollback-model
    p_rb = sub.add_parser('rollback-model', help='Rollback to previously deployed model')
    p_rb.add_argument('--target-version', required=True)
    p_rb.add_argument('--actor', required=True)
    p_rb.add_argument('--reason', required=True)
    p_rb.add_argument('--model-dir', default='runs/fd001-v1')
    p_rb.add_argument('--environment', default='local')
    p_rb.set_defaults(func=cmd_rollback_model)

    p_sync = sub.add_parser('sync-release-pointer', help='Recover pointer from committed release metadata')
    p_sync.set_defaults(func=cmd_sync_release_pointer)

    # list-deployments
    p_ld = sub.add_parser('list-deployments', help='List deployment audit history')
    p_ld.add_argument('--limit', type=int, default=50)
    p_ld.add_argument('--offset', type=int, default=0)
    p_ld.set_defaults(func=cmd_list_deployments)

    # status
    p_st = sub.add_parser('status', help='View desired vs active deployment status')
    p_st.set_defaults(func=cmd_status)

    # run-drift-monitoring
    p_dm = sub.add_parser('run-drift-monitoring', help='Evaluate input drift on recent predictions')
    p_dm.add_argument('--tenant-id', required=True)
    p_dm.add_argument('--model-version', default='fd001-v1')
    p_dm.add_argument('--actor', default='operator:monitoring')
    p_dm.add_argument('--min-samples', type=int, default=5)
    p_dm.add_argument('--drift-threshold', type=float, default=3.0)
    p_dm.set_defaults(func=cmd_drift_monitoring)

    # run-evaluation
    p_ev = sub.add_parser('run-evaluation', help='Evaluate predictions against ground-truth labels')
    p_ev.add_argument('--tenant-id', required=True)
    p_ev.add_argument('--labels-path', default='data/raw/RUL_FD001.txt')
    p_ev.add_argument('--subset', default='FD001')
    p_ev.add_argument('--partition', default='test')
    p_ev.add_argument('--model-version', default='fd001-v1')
    p_ev.add_argument('--actor', default='operator:evaluation')
    p_ev.add_argument('--expected-sha256', default=None)
    p_ev.set_defaults(func=cmd_evaluate)

    args = p.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
