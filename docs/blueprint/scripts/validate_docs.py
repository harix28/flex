"""Standard-library consistency checks for this documentation pack, not app tests."""
import json,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
errors=[]
def fail(msg):errors.append(msg)
for p in ROOT.rglob('*.md'):
    s=p.read_text()
    if s.count('```')%2:fail(f'{p.name}: unbalanced code fence')
    for target in re.findall(r'\]\(([^)]+)\)',s):
        if '://' in target or target.startswith('#'):continue
        target=target.split('#')[0]
        if not (p.parent/target).exists():fail(f'{p.name}: missing link {target}')
spec=json.loads((ROOT/'contracts/openapi.json').read_text())
def refs(o):
    if isinstance(o,dict):
        if '$ref' in o:
            ref=o['$ref']
            if ref.startswith('#/'):
                v=spec
                try:
                    for x in ref[2:].split('/'):v=v[x]
                except (KeyError,TypeError):fail('Unresolved OpenAPI reference '+ref)
            else:fail('Unexpected nonlocal OpenAPI reference '+ref)
        for v in o.values():refs(v)
    elif isinstance(o,list):
        for v in o:refs(v)
refs(spec)
ids=[]
for path,methods in spec['paths'].items():
    placeholders=set(re.findall(r'{([^}]+)}',path))
    for method,op in methods.items():
        ids.append(op['operationId'])
        declared={p['name'] for p in op.get('parameters',[]) if p['in']=='path' and p.get('required')}
        if placeholders!=declared:fail(f'{method} {path}: path parameters differ')
        if not op.get('security'):fail(f'{path}: no authentication contract')
        if method=='post' and not any(p['name']=='Idempotency-Key' for p in op.get('parameters',[])):fail(f'{path}: missing idempotency')
if len(ids)!=len(set(ids)):fail('Duplicate operation ID')

def validate(value,schema,label):
    # Lightweight structural validation only. Full JSON Schema conformance belongs in CI.
    if '$ref' in schema:
        validate(value,spec['components']['schemas'][schema['$ref'].split('/')[-1]],label);return
    types=schema.get('type');types=[types] if isinstance(types,str) else types
    actual='null' if value is None else 'boolean' if isinstance(value,bool) else 'integer' if isinstance(value,int) else 'number' if isinstance(value,float) else 'string' if isinstance(value,str) else 'array' if isinstance(value,list) else 'object'
    if types and actual not in types and not (actual=='integer' and 'number' in types):fail(label+': wrong type');return
    if 'enum' in schema and value not in schema['enum']:fail(label+': enum mismatch')
    if 'const' in schema and value!=schema['const']:fail(label+': const mismatch')
    if value is None:return
    if isinstance(value,dict):
        for k in schema.get('required',[]):
            if k not in value:fail(label+': missing '+k)
        props=schema.get('properties',{})
        if schema.get('additionalProperties') is False:
            for k in set(value)-set(props):fail(label+': extra field '+k)
        for k,v in value.items():
            if k in props:validate(v,props[k],label+'.'+k)
    if isinstance(value,list):
        if len(value)<schema.get('minItems',0) or len(value)>schema.get('maxItems',float('inf')):fail(label+': array size')
        for i,v in enumerate(value):validate(v,schema.get('items',{}),label+f'[{i}]')
    if isinstance(value,(int,float)) and not isinstance(value,bool):
        if value<schema.get('minimum',-float('inf')) or value>schema.get('maximum',float('inf')):fail(label+': range')
schema=json.loads((ROOT/'contracts/telemetry.schema.json').read_text())
validate(json.loads((ROOT/'examples/telemetry.json').read_text()),schema,'telemetry example')
validate(json.loads((ROOT/'examples/prediction.json').read_text()),spec['components']['schemas']['Prediction'],'prediction example')
sql=(ROOT/'database/schema.sql').read_text()
tables=set(re.findall(r'CREATE TABLE (\w+)',sql))
for target in re.findall(r'REFERENCES (\w+)\(',sql):
    if target not in tables:fail('Unknown SQL reference '+target)
if errors:
    print('\n'.join(errors));sys.exit(1)
print(f'PASS: {len(list(ROOT.rglob("*.md")))} Markdown files; {len(ids)} API operations; local links, schema refs, examples and SQL reference names consistent.')
print('Not covered: PostgreSQL execution, full schema semantics, application behavior, security, ML quality or production readiness.')
