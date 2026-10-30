"""Build a sanitized, indexed AI documentation bundle without deploying or reading DB data.

Run from the repository virtual environment. Source snapshots are context, not a
runnable distribution. Private environment values are read only into the redactor;
they are never printed or included in the archive.
"""
from __future__ import annotations

import ast
import hashlib
import json
import re
import secrets
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs' / 'AI_HANDOFF'
sys.path.insert(0, str(ROOT))
TEXT_EXTENSIONS = {'.py', '.md', '.ts', '.tsx', '.js', '.jsx', '.css', '.html', '.sql',
                   '.json', '.yml', '.yaml', '.toml', '.ini', '.sh', '.ps1', '.conf', '.txt'}
SOURCE_ROOTS = {'sentinel', 'tests', 'apps', 'database', 'docs', 'packages', 'scripts',
                'config', 'infra', 'backend', 'frontend', '.github', 'resources'}
BLOCKED_PARTS = {'node_modules', '__pycache__', '.venv', '.git', '.runtime', 'dist',
                 '.pytest_cache', 'tls', 'source_snapshot'}
MODEL_METADATA = {'bundle.json', 'report.json', 'config.json', 'split.json', 'forest.json',
                  'manifest.json', 'results.json', 'frozen_selections.json', 'feature_selection.json',
                  'validation.json', 'test_audit.json'}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def git(*args):
    return subprocess.run(['git', *args], cwd=ROOT, capture_output=True, check=True).stdout


def private_values():
    values = set()
    files = list(ROOT.glob('.env*')) + list((ROOT / '.runtime').glob('*.env'))
    for path in files:
        if path.name.endswith('.example'):
            continue
        for line in path.read_text(encoding='utf-8-sig', errors='replace').splitlines():
            key, sep, value = line.partition('=')
            if sep and re.search(r'PASSWORD|SECRET|TOKEN|API_KEY|DATABASE_URL|PRIVATE_KEY', key, re.I):
                value = value.strip().strip('"\'')
                if len(value) >= 6 and not value.startswith(('${', '<')):
                    values.add(value)
                    if '://' in value and '@' in value:
                        credentials = value.split('://', 1)[1].split('@', 1)[0]
                        if ':' in credentials and len(credentials.split(':', 1)[1]) >= 6:
                            values.add(credentials.split(':', 1)[1])
    return sorted(values, key=len, reverse=True)


def clean(value, sensitive):
    for item in sensitive:
        value = value.replace(item, '<REDACTED_PRIVATE_VALUE>')
    for root in (str(ROOT), ROOT.as_posix(), str(Path.home()), Path.home().as_posix()):
        value = value.replace(root, '<LOCAL_PATH>')
        value = value.replace(root.replace('\\', '\\\\'), '<LOCAL_PATH>')
    def scrub_url(match):
        text = match.group(0)
        return text if '${' in text or '<' in text else match.group(1) + '<REDACTED_CREDENTIALS>@'
    value = re.sub(r'((?:postgresql(?:\+psycopg)?|https?)://)[^\s/\"\']+:[^\s/\"\']+@', scrub_url, value)
    value = re.sub(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
                   '<REDACTED_PRIVATE_KEY>', value)
    return value


def select(path):
    parts = Path(path).parts
    name = parts[-1]
    if path.startswith('docs/AI_HANDOFF/') or name.startswith('MERIDIAN_SENTINEL_AI_'):
        return 'generated handoff output; indexed separately'
    if any(p in BLOCKED_PARTS for p in parts):
        return 'private, generated or third-party runtime content'
    if '.env' in name and not name.endswith('.example'):
        return 'private environment configuration'
    if name.endswith(('.pem', '.key', '.pfx', '.p12', '.sqlite', '.sqlite3')):
        return 'private key or database'
    if parts[0] == 'runs' and name in MODEL_METADATA:
        return None
    if parts[0] in {'runs', 'data', 'archives', 'ml_package'} or path == 'request.json':
        return 'dataset, model artifact, older export or raw request'
    if parts[0] == 'reports' and Path(name).suffix != '.md':
        return 'generated report data/media; text reports retained'
    allowed_name = name.startswith('Dockerfile') or name in {'Makefile', '.gitignore', '.dockerignore', '.gitattributes'} or name.endswith('.example')
    if Path(name).suffix not in TEXT_EXTENSIONS and not allowed_name:
        return 'binary/media or non-text artifact'
    if len(parts) > 1 and parts[0] not in SOURCE_ROOTS | {'reports'}:
        return 'outside declared first-party documentation/source roots'
    return None


def analyze(path, source):
    result = {'symbols': [], 'routes': [], 'imports': [], 'cli_arguments': [], 'tests': []}
    if not path.endswith('.py'):
        if path.endswith(('.ts', '.tsx')):
            result['symbols'] = [{'name': name, 'line': source[:m.start()].count('\n')+1}
                for m in re.finditer(r'export\s+(?:default\s+)?(?:const|function|class|interface|type)\s+(\w+)', source)
                for name in [m.group(1)]]
            result['tests'] = re.findall(r'\b(?:it|test)\s*\(\s*[\'\"]([^\'\"]+)', source)
        return result
    try:
        tree = ast.parse(source)
    except SyntaxError:
        result['parse_error'] = True
        return result
    prefix = ''
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'APIRouter':
            for kw in node.keywords:
                if kw.arg == 'prefix' and isinstance(kw.value, ast.Constant):
                    prefix = kw.value.value
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            is_class = isinstance(node, ast.ClassDef)
            signature = node.name if is_class else node.name + '(' + ast.unparse(node.args) + ')'
            result['symbols'].append({'name': node.name, 'signature': signature, 'line': node.lineno,
                                      'kind': 'class' if is_class else 'function', 'doc': ast.get_docstring(node) or ''})
            if node.name.startswith('test_'):
                result['tests'].append(node.name)
            for dec in node.decorator_list:
                if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute) and dec.func.attr in {'get','post','put','patch','delete','head','options'} and dec.args and isinstance(dec.args[0], ast.Constant):
                    result['routes'].append({'method': dec.func.attr.upper(), 'path': prefix + str(dec.args[0].value),
                                             'handler': node.name, 'line': node.lineno, 'signature': signature})
        if isinstance(node, ast.Import):
            result['imports'].extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            result['imports'].append('.'*node.level + (node.module or '') + ':' + ','.join(a.name for a in node.names))
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in {'add_argument','add_parser'}:
            result['cli_arguments'].append({'line': node.lineno, 'declaration': ast.unparse(node)})
    return result


def write(name, value):
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding='utf-8', newline='\n')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    sensitive = private_values()
    paths = sorted(set(p.decode('utf-8') for p in git('ls-files','--cached','--others','--exclude-standard','-z').split(b'\0') if p))
    paths = sorted(set(paths) | {p.relative_to(ROOT).as_posix() for p in (ROOT/'runs').rglob('*.json') if p.name in MODEL_METADATA})
    entries, excluded, sources = [], [], {}
    for path in paths:
        reason = select(path)
        actual = ROOT / path
        if reason or not actual.is_file():
            excluded.append({'path': path, 'reason': reason or 'not a current regular file'})
            continue
        raw = actual.read_bytes()
        try:
            source = raw.decode('utf-8-sig')
        except UnicodeError:
            excluded.append({'path': path, 'reason': 'not UTF-8 text'})
            continue
        if '\x00' in source:
            excluded.append({'path': path, 'reason': 'binary signature'})
            continue
        exported = clean(source, sensitive)
        analysis = analyze(path, source)
        entry = {'path': path, 'source_sha256': digest(raw), 'source_bytes': len(raw),
                 'lines': len(source.splitlines()), 'export_sha256': digest(exported.encode()),
                 'sanitized': exported != source, **analysis}
        entries.append(entry)
        sources[path] = exported
        write('source_snapshot/' + path, exported)

    artifacts = []
    for directory in (ROOT/'runs', ROOT/'data'/'raw'):
        for path in sorted(directory.rglob('*')):
            if path.is_file():
                rel = path.relative_to(ROOT).as_posix()
                artifacts.append({'path': rel, 'bytes': path.stat().st_size,
                                  'content_included': rel in sources,
                                  'role': 'model/experiment artifact' if rel.startswith('runs/') else 'raw dataset prerequisite'})
    write('ARTIFACT_INVENTORY.json', json.dumps(artifacts, indent=2))

    # Construct schemas without model configuration, network service, DB or lifespan.
    openapi_error = None
    try:
        from sentinel.api import create_app
        from sentinel.config import Settings
        app = create_app(settings=Settings(api_key=secrets.token_urlsafe(32)))
        schema = app.openapi()
        write('runtime.openapi.json', json.dumps(schema, indent=2, ensure_ascii=False))
    except Exception as exc:
        schema = {}
        openapi_error = type(exc).__name__
        write('runtime.openapi.json', json.dumps({'generation_error_type': openapi_error}))

    sections = ['# Generated technical reference', '',
        'Generated from the selected working-tree sources. Static routes/symbols establish declarations, not successful execution.',
        'Source paths below resolve beneath `source_snapshot/`. Complete source files accompany this index.', '',
        '## 1. Runtime OpenAPI endpoint inventory', '', '| Method | Path | Operation ID | Summary |', '|---|---|---|---|']
    route_count = 0
    for path, methods in sorted(schema.get('paths', {}).items()):
        for method, data in methods.items():
            if method.lower() not in {'get','post','put','patch','delete','head','options'}:
                continue
            route_count += 1
            sections.append(f"| {method.upper()} | `{path}` | `{data.get('operationId','')}` | {data.get('summary','').replace('|','/')} |")
    if openapi_error:
        sections.append('Runtime export failed with ' + openapi_error + '; use static route declarations below.')
    sections += ['', '## 2. Static route declarations and handler contracts', '']
    for e in entries:
        if e['routes']:
            sections += ['### ' + e['path'], '']
            for r in e['routes']:
                sections += [f"- `{r['method']} {r['path']}` — line {r['line']}; `{r['signature']}`"]
            sections += ['']
    sections += ['## 3. Declared request/response schemas', '',
                 'These are the app-generated schemas; not all legacy handlers declare response models. Exact service output remains in source.', '']
    for name, definition in sorted(schema.get('components', {}).get('schemas', {}).items()):
        sections += ['### ' + name, '', '```json', json.dumps(definition, indent=2, ensure_ascii=False), '```', '']
    sections += ['## 4. Complete executable migration definitions', '',
                 'Only database/migrations/versions is executable migration history. Reference and blueprint schemas are separate planned designs.', '']
    for path, source in sources.items():
        if path.startswith('database/migrations/versions/'):
            sections += ['### ' + path, '', '````' + ('sql' if path.endswith('.sql') else 'python'), source, '````', '']
    sections += ['## 5. Source modules, symbols and imports', '']
    for e in entries:
        if not e['symbols'] and not e['path'].endswith('.py'):
            continue
        sections += ['### ' + e['path'], '', f"{e['lines']} lines; source SHA-256 `{e['source_sha256']}`.", '']
        if not e['source_bytes']:
            sections += ['**EMPTY FILE at capture.**', '']
        if e['imports']:
            sections += ['Imports: ' + '; '.join('`'+v+'`' for v in sorted(set(e['imports']))) + '.', '']
        for symbol in e['symbols']:
            sections.append(f"- Line {symbol['line']}: `{symbol.get('signature',symbol['name'])}`")
            if symbol.get('doc'):
                sections.append('  Declared docstring (not independently verified): ' + symbol['doc'].splitlines()[0])
        sections += ['']
    sections += ['## 6. CLI argument declarations', '']
    for e in entries:
        if e['cli_arguments']:
            sections += ['### ' + e['path'], '', '```python']
            sections += [x['declaration'] for x in e['cli_arguments']]
            sections += ['```', '']
    sections += ['## 7. Test inventory', '', 'Names are definitions, not passing test results; parameterized cases expand at collection.', '']
    test_definitions = 0
    for e in entries:
        if e['tests']:
            test_definitions += len(e['tests'])
            sections += ['### ' + e['path'], ''] + ['- `'+t+'`' for t in e['tests']] + ['']
    sections += ['## 8. Configuration identifiers (names only)', '']
    env = set()
    for source in sources.values():
        env.update(re.findall(r'\b(?:SENTINEL_[A-Z_0-9]+|DATABASE_URL|MIGRATION_DATABASE_URL|POSTGRES_[A-Z_0-9]+|VITE_[A-Z_0-9]+|BACKEND_URL|GATEWAY_[A-Z_0-9]+|RENDER_EXTERNAL_URL|FORWARDED_ALLOW_IPS)\b', source))
    sections += ['- `'+v+'`' for v in sorted(env)]
    sections += ['', '## 9. Dependency and build declarations', '']
    for path in ('requirements.txt','requirements.lock.txt','requirements.windows.lock.txt','package.json','apps/web/package.json','docker-compose.yml','docker-compose.dev.yml','.github/workflows/backend-tests.yml'):
        if path in sources:
            sections += ['### ' + path, '', '````text', sources[path], '````', '']
    sections += ['## 10. Complete selected file inventory', '', '| Path | Lines | Bytes | Sanitized |', '|---|---:|---:|---|']
    for e in entries:
        sections.append(f"| `{e['path']}` | {e['lines']} | {e['source_bytes']} | {e['sanitized']} |")
    sections += ['', '## 11. Excluded indexed paths', '',
                 'Ignored runtime/data directories are excluded by category and not recursively enumerated. This is not a listing of private database or environment contents.', '']
    for e in excluded:
        sections.append(f"- `{e['path']}`: {e['reason']}")
    sections += ['', '## 12. Model metadata and local artifact inventory', '',
                 'Safe JSON model manifests, evaluation summaries, splits and feature selections are bundled under source_snapshot/runs. Model weights, raw input rows and per-row prediction exports are not included. Existence/size is not activation or deployment evidence.', '']
    for path, source in sources.items():
        if path.startswith('runs/'):
            sections += ['### ' + path, '', '````json', source, '````', '']
    sections += ['| Local artifact | Bytes | Content included |', '|---|---:|---|']
    sections += [f"| `{a['path']}` | {a['bytes']} | {a['content_included']} |" for a in artifacts]
    write('02_TECHNICAL_REFERENCE.md', clean('\n'.join(sections), sensitive))

    changed = [e['path'] for e in entries if not (ROOT/e['path']).exists() or digest((ROOT/e['path']).read_bytes()) != e['source_sha256']]
    manifest = {'generated_utc': datetime.now(timezone.utc).isoformat(), 'user_timezone': 'Asia/Calcutta',
                'git_head': git('rev-parse','HEAD').decode().strip(), 'git_branch': git('branch','--show-current').decode().strip(),
                'working_tree_status': clean(git('status','--short').decode('utf-8'), sensitive),
                'scope': 'selected first-party source/docs/tests/configuration; sanitized; no private runtime/data/models',
                'inputs_changed_during_capture': changed, 'runtime_openapi_error': openapi_error,
                'files': entries, 'excluded_paths': excluded}
    write('MANIFEST.json', clean(json.dumps(manifest, indent=2, ensure_ascii=False), sensitive))

    order = ['00_READ_FIRST.md','03_CURRENT_GAPS_AND_CONTRADICTIONS.md','01_PROJECT_MASTER.md',
             '04_AI_WORKING_INSTRUCTIONS.md','05_VALIDATION_AND_PROVENANCE.md','02_TECHNICAL_REFERENCE.md']
    combined = '\n\n---\n\n'.join((OUT/name).read_text(encoding='utf-8') for name in order)
    (ROOT/'MERIDIAN_SENTINEL_AI_CONTEXT.md').write_text(clean(combined, sensitive), encoding='utf-8', newline='\n')
    bundle_paths = [OUT/name for name in order] + [OUT/'runtime.openapi.json', OUT/'MANIFEST.json', OUT/'ARTIFACT_INVENTORY.json']
    bundle_paths += [OUT/'source_snapshot'/e['path'] for e in entries]
    found = []
    for path in bundle_paths + [ROOT/'MERIDIAN_SENTINEL_AI_CONTEXT.md']:
        content = path.read_text(encoding='utf-8')
        if any(value in content for value in sensitive):
            found.append(path.relative_to(ROOT).as_posix())
    mismatches = [e['path'] for e in entries if digest((OUT/'source_snapshot'/e['path']).read_bytes()) != e['export_sha256']]
    validation = {'included_source_files': len(entries), 'runtime_api_operations': route_count,
                  'runtime_component_schemas': len(schema.get('components',{}).get('schemas',{})),
                  'test_definitions_indexed': test_definitions, 'source_files_changed': changed,
                  'export_hash_mismatches': mismatches, 'local_artifacts_inventoried': len(artifacts),
                  'recognized_secret_scan_findings': found, 'openapi_generation_error': openapi_error,
                  'combined_document_words': len(combined.split()), 'combined_document_bytes': len(combined.encode()),
                  'note': 'Documentation/index validation, not an application test run; source snapshot intentionally excludes live data and secrets.'}
    write('EXPORT_VALIDATION.json', json.dumps(validation, indent=2))
    bundle_paths.append(OUT/'EXPORT_VALIDATION.json')
    if found or changed or mismatches:
        print(json.dumps(validation))
        raise SystemExit('Export requires review; no new archive published')
    checksums = {p.relative_to(OUT).as_posix(): digest(p.read_bytes()) for p in bundle_paths}
    write('BUNDLE_SHA256.json', json.dumps(checksums, indent=2))
    bundle_paths.append(OUT/'BUNDLE_SHA256.json')
    archive = ROOT/'docs'/'MERIDIAN_SENTINEL_AI_HANDOFF.zip'
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for path in bundle_paths:
            z.write(path, 'AI_HANDOFF/' + path.relative_to(OUT).as_posix())
        z.write(ROOT/'MERIDIAN_SENTINEL_AI_CONTEXT.md', 'MERIDIAN_SENTINEL_AI_CONTEXT.md')
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None:
            raise SystemExit('Archive integrity check failed')
    print(json.dumps({**validation, 'archive_bytes': archive.stat().st_size}, indent=2))


if __name__ == '__main__':
    main()
