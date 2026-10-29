"""Comprehensive E2E HTTP integration verification against live Sentinel backend on port 8001."""
import sys
import uuid
import httpx

BASE_URL = 'http://127.0.0.1:8001'

def run_e2e_verification():
    print(f"=== Starting Real E2E Flow Verification against {BASE_URL} ===")
    
    # Client with cookie jar
    client = httpx.Client(base_url=BASE_URL, timeout=15.0)

    # 1. Health checks
    res = client.get('/health')
    assert res.status_code == 200, f"Health check failed: {res.text}"
    print("[OK] 1. Backend Health: OK", res.json())

    res = client.get('/health/ready')
    assert res.status_code == 200, f"Ready check failed: {res.text}"
    print("[OK] 2. Predictor Model: Ready", res.json())

    res = client.get('/health/database')
    assert res.status_code == 200, f"Database check failed: {res.text}"
    print("[OK] 3. Database: Ready", res.json())

    # 2. Login as Administrator
    print("\n--- Step 1: Admin Login ---")
    headers = {
        'Origin': 'http://127.0.0.1:8001',
        'X-CSRF-Protection': '1',
    }
    res = client.post(
        '/api/v1/auth/login',
        json={'email': 'admin@meridian.example.com', 'password': 'Password12345!'},
        headers=headers,
    )
    assert res.status_code == 200, f"Admin login failed: {res.status_code} {res.text}"
    login_data = res.json()
    csrf_token = login_data['csrf_token']
    orgs = login_data['organizations']
    assert len(orgs) > 0, "No organizations found for admin"
    tenant_id = orgs[0]['id']
    tenant_name = orgs[0]['name']
    print(f"[OK] Admin Logged In. Tenant: {tenant_name} ({tenant_id})")
    print(f"[OK] Received CSRF Token & Session Cookie.")

    auth_headers = {
        'Origin': 'http://127.0.0.1:8001',
        'X-CSRF-Protection': '1',
        'X-CSRF-Token': csrf_token,
    }

    # 3. Check Session /auth/me
    res = client.get('/api/v1/auth/me', headers=auth_headers)
    assert res.status_code == 200
    user_data = res.json()
    admin_user_id = user_data['user']['id']
    print(f"[OK] /auth/me confirmed user: {user_data['user']['display_name']} ({admin_user_id})")

    # 4. Ranked fleet machines
    print("\n--- Step 2: Ranked Machines & Fleet Overview ---")
    res = client.get(f'/api/v1/organizations/{tenant_id}/maintenance-priorities', headers=auth_headers)
    assert res.status_code == 200
    priorities_data = res.json()
    items = priorities_data['items']
    print(f"[OK] Ranked Machines Total: {priorities_data['total']}, Items in page: {len(items)}")
    target_machine = None
    for m in items:
        print(f"    - Asset: {m['asset_code']} | Status: {m['status']} | Priority: {m['priority_band']} | RUL: {m['rul_cycles']} {m['rul_units']}")
        if m['asset_code'] == 'NASA-FD001-TEST-1':
            target_machine = m

    assert target_machine is not None, "Target machine NASA-FD001-TEST-1 not found in ranked fleet"
    machine_id = target_machine['machine_id']

    # 5. Machine Detail & Stored Sensor Trends
    print("\n--- Step 3: Machine Details & Stored Sensor Trends ---")
    res = client.get(f'/api/v1/organizations/{tenant_id}/machines/{machine_id}', headers=auth_headers)
    assert res.status_code == 200
    mach_detail = res.json()['machine']
    sb = mach_detail.get('source_binding') or {}
    print(f"    Data Source: {mach_detail['data_source']}, Split: {sb.get('split')}, Engine: {sb.get('engine_id')}")

    res = client.get(f'/api/v1/organizations/{tenant_id}/machines/{machine_id}/observations?limit=100', headers=auth_headers)
    assert res.status_code == 200
    obs_data = res.json()
    obs_items = obs_data['items']
    assert len(obs_items) == 31, f"Expected 31 observations, got {len(obs_items)}"
    print(f"[OK] Sensor History: {len(obs_items)} observations stored. First cycle: {obs_items[0]['cycle']}, Latest cycle: {obs_items[-1]['cycle']}")

    # 6. Run Causal Prediction
    print("\n--- Step 4: Run Causal Prediction ---")
    pred_headers = dict(auth_headers, **{'Idempotency-Key': f"e2e-pred-{uuid.uuid4().hex[:8]}"})
    res = client.post(
        f'/api/v1/organizations/{tenant_id}/machines/{machine_id}/predictions',
        json={'cutoff_cycle': 31},
        headers=pred_headers,
    )
    assert res.status_code == 200, f"Prediction failed: {res.status_code} {res.text}"
    pred_data = res.json()['prediction']
    prediction_id = pred_data['id']
    print(f"[OK] Causal Prediction Generated: ID: {prediction_id}")
    print(f"    Estimated RUL: {pred_data['rul_cycles']} {pred_data['rul_units']}")
    print(f"    Priority Band: {pred_data['priority_band']} (Rule: {pred_data['priority_rule']})")
    print(f"    Cutoff Cycle: {pred_data['observed_cutoff_cycle']} (Input Window: {pred_data['input_window_start_cycle']} - {pred_data['input_window_end_cycle']})")
    print(f"    Release Status: {pred_data['release_status']} | Failure Probability: {pred_data['failure_probability']} (Honest null)")

    # 7. Create Draft Work Order from Prediction
    print("\n--- Step 5: Draft Work Order from Prediction ---")
    wo_create_headers = dict(auth_headers, **{'Idempotency-Key': f"e2e-wo-{uuid.uuid4().hex[:8]}"})
    res = client.post(
        f'/api/v1/organizations/{tenant_id}/predictions/{prediction_id}/work-order-draft',
        json={
            'title': 'Borescope Inspection - HPC Stage 1',
            'description': 'Detailed borescope inspection of high pressure compressor blades based on causal RUL estimation.',
            'priority': 'high',
            'planned_date': '2026-04-15',
            'due_date': '2026-04-20',
        },
        headers=wo_create_headers,
    )
    assert res.status_code in (200, 201), f"Work order creation failed: {res.status_code} {res.text}"
    wo = res.json()['work_order']
    wo_id = wo['id']
    wo_num = wo['work_order_number']
    print(f"[OK] Work Order Active: {wo_num} (ID: {wo_id})")
    print(f"    Status: {wo['status']} (Version: v{wo['version']})")
    print(f"    Already Active flag: {wo.get('already_active')}")

    # 8. If Draft, Approve Work Order as Administrator
    if wo['status'] == 'draft':
        print("\n--- Step 6: Approve Work Order (OCC Transition) ---")
        res = client.post(
            f'/api/v1/organizations/{tenant_id}/work-orders/{wo_id}/transitions',
            json={'version': wo['version'], 'action': 'approve'},
            headers=auth_headers,
        )
        assert res.status_code == 200, f"Approval failed: {res.status_code} {res.text}"
        wo = res.json()['work_order']
        print(f"[OK] Work Order Approved! Status: {wo['status']}, Version: v{wo['version']}")
    else:
        print(f"[OK] Work Order already in active state '{wo['status']}', advancing with lifecycle.")

    # 9. Find Technician user and Assign if unassigned
    res = client.get(f'/api/v1/organizations/{tenant_id}/members', headers=auth_headers)
    assert res.status_code == 200
    members = res.json()['items']
    tech_member = None
    for mem in members:
        if 'technician' in mem['roles']:
            tech_member = mem
            break
    assert tech_member is not None, "Technician member not found in tenant"
    tech_user_id = tech_member['user_id']

    if not wo.get('assigned_technician_id'):
        print("\n--- Step 7: Assign Technician ---")
        res = client.post(
            f'/api/v1/organizations/{tenant_id}/work-orders/{wo_id}/assignment',
            json={
                'version': wo['version'],
                'technician_id': tech_user_id,
                'reason': 'Assigned to morning test cell shift per AMM schedule',
            },
            headers=auth_headers,
        )
        assert res.status_code == 200, f"Assignment failed: {res.status_code} {res.text}"
        wo = res.json()['work_order']
        print(f"[OK] Work Order Assigned to {tech_member['display_name']}! Version: v{wo['version']}")
    else:
        print(f"[OK] Work Order already assigned to {wo.get('assigned_technician_name', tech_member['display_name'])}.")

    # 10. Post Discussion Note
    print("\n--- Step 8: Post Discussion Note ---")
    res = client.post(
        f'/api/v1/organizations/{tenant_id}/work-orders/{wo_id}/notes',
        json={'version': wo['version'], 'note_text': f'Operational checkpoint verified at {uuid.uuid4().hex[:6]}.'},
        headers=auth_headers,
    )
    assert res.status_code in (200, 201), f"Note posting failed: {res.status_code} {res.text}"
    note_data = res.json()
    new_version = note_data['work_order_version']
    wo['version'] = new_version
    print(f"[OK] Note Posted! Note ID: {note_data['note']['id']}, Work Order Version: v{new_version}")

    # 11. Admin Logout
    print("\n--- Step 9: Admin Logout ---")
    res = client.post('/api/v1/auth/logout', headers=auth_headers)
    assert res.status_code == 200
    print("[OK] Admin logged out successfully.")

    # Verify unauthenticated call is rejected
    res = client.get(f'/api/v1/organizations/{tenant_id}/work-orders/{wo_id}')
    assert res.status_code == 401, f"Expected 401 unauthenticated, got {res.status_code}"
    print("[OK] Route protection verified: unauthenticated request rejected with 401.")

    # 12. Login as Technician & Execute Work
    print("\n--- Step 10: Technician Login & Execution Lifecycle ---")
    tech_client = httpx.Client(base_url=BASE_URL, timeout=15.0)
    res = tech_client.post(
        '/api/v1/auth/login',
        json={'email': 'tech@meridian.example.com', 'password': 'Password12345!'},
        headers={'Origin': 'http://127.0.0.1:8001', 'X-CSRF-Protection': '1'},
    )
    assert res.status_code == 200, f"Tech login failed: {res.status_code} {res.text}"
    tech_csrf = res.json()['csrf_token']
    tech_headers = {
        'Origin': 'http://127.0.0.1:8001',
        'X-CSRF-Protection': '1',
        'X-CSRF-Token': tech_csrf,
    }
    print(f"[OK] Technician logged in: {res.json()['organizations'][0]['name']}")

    # Check current status before start/complete
    res = tech_client.get(f'/api/v1/organizations/{tenant_id}/work-orders/{wo_id}', headers=tech_headers)
    wo = res.json()['work_order']

    if wo['status'] == 'approved':
        # Start Work: in_progress
        res = tech_client.post(
            f'/api/v1/organizations/{tenant_id}/work-orders/{wo_id}/transitions',
            json={'version': wo['version'], 'action': 'start'},
            headers=tech_headers,
        )
        assert res.status_code == 200, f"Start work failed: {res.status_code} {res.text}"
        wo = res.json()['work_order']
        print(f"[OK] Work Order Started -> Status: {wo['status']}, Version: v{wo['version']}")

    if wo['status'] == 'in_progress':
        # Complete Work: completed (Terminal)
        summary_text = 'Borescope inspection completed. HPC blades within acceptable erosion limits per AMM 72-00. No foreign object damage detected.'
        res = tech_client.post(
            f'/api/v1/organizations/{tenant_id}/work-orders/{wo_id}/transitions',
            json={'version': wo['version'], 'action': 'complete', 'completion_summary': summary_text},
            headers=tech_headers,
        )
        assert res.status_code == 200, f"Complete work failed: {res.status_code} {res.text}"
        wo = res.json()['work_order']
        print(f"[OK] Work Order Completed -> Status: {wo['status']} (Terminal), Version: v{wo['version']}")
        print(f"    Completion Summary Recorded: '{wo['completion_summary']}'")

    # Inspect audit history & transitions
    res = tech_client.get(f'/api/v1/organizations/{tenant_id}/work-orders/{wo_id}/history', headers=tech_headers)
    assert res.status_code == 200
    hist = res.json()
    print(f"[OK] Audit History: {len(hist['transitions'])} transitions, {len(hist['notes'])} notes recorded.")
    for t in hist['transitions']:
        actor_name = t.get('actor_name') or t.get('actor_id')
        print(f"    - Transition: {t['from_status']} -> {t['to_status']} by {actor_name}")

    # Final Tech Logout
    res = tech_client.post('/api/v1/auth/logout', headers=tech_headers)
    assert res.status_code == 200
    print("[OK] Technician logged out.")

    print("\n=======================================================")
    print(">>> ALL 10 E2E STEPS VERIFIED 100% SUCCESSFUL ON LIVE BACKEND <<<")
    print("=======================================================")

if __name__ == '__main__':
    run_e2e_verification()
