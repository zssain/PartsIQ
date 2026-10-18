from pathlib import Path
import json,re,hashlib
R=Path(__file__).resolve().parents[1]
checks=[]
def check(name,passed,detail):
 checks.append(dict(check=name,passed=bool(passed),detail=detail))
 print(('PASS ' if passed else 'FAIL ')+name+': '+str(detail))
fs=json.loads((R/'spec/features.json').read_text());ps=json.loads((R/'spec/prompts.json').read_text());order=json.loads((R/'spec/build-order.json').read_text());eps=json.loads((R/'spec/endpoints.json').read_text());manifest=json.loads((R/'spec/file-ownership.json').read_text())
check('69 feature IDs',[f['id'] for f in fs]==[f'F{i:02}' for i in range(1,70)],len(fs))
check('97 prompts',len(ps)==97 and all((R/p['path']).is_file() for p in ps.values()),len(ps))
check('69 traces and test mappings',all((R/f['trace']).is_file() and f['test'] in ps[f['id']]['tests'] for f in fs),len(fs))
pos={k:i for i,k in enumerate(order)};bad=[(k,d) for k,p in ps.items() for d in p['depends_on'] if d not in pos or pos[d]>=pos[k]]
check('No forward declared dependencies',not bad,bad)
paths=[x['path'] for x in manifest];check('One creator per planned file',len(paths)==len(set(paths)) and all(x['created_by'] in ps and x['path'] in ps[x['created_by']]['creates'] for x in manifest),len(paths))
req=(R/'spec/python-requirements.in').read_text();lock=(R/'spec/python-requirements.lock').read_text()
check('No agent runtime dependencies',not any(x in req+lock for x in ('langgraph','langchain','crewai')), 'Python manifests and lock')
check('CPU wheel', 'torch-2.10.0%2Bcpu' in lock and 'nvidia-' not in lock,'CPU target')
check('77 unique REST operations',len(eps)==77 and len({(e['method'],e['path']) for e in eps})==77,len(eps))
api=json.loads((R/'spec/openapi.json').read_text());schemas=api['components']['schemas'];badrefs=[]
def walk(v):
 if isinstance(v,dict):
  if '$ref' in v and v['$ref'].startswith('#/components/schemas/') and v['$ref'].split('/')[-1] not in schemas:badrefs.append(v['$ref'])
  for x in v.values():walk(x)
 elif isinstance(v,list):
  for x in v:walk(x)
walk(api);check('OpenAPI references',not badrefs,badrefs)
sections=re.findall(r'^## (.+)$',(R/'docs/templates/PROMPT_TEMPLATE.md').read_text(),re.M)
bad=[k for k,p in ps.items() if re.findall(r'^## (.+)$',(R/p['path']).read_text(),re.M)!=sections];check('Prompt template parity',not bad,bad)
short=[k for k,p in ps.items() if len((R/p['path']).read_text().split())<1000];check('Detailed prompts above1000words',not short,short)
sql='\n'.join(p.read_text() for p in (R/'spec/sql').glob('*.sql'));tables=set(re.findall(r'CREATE TABLE(?: IF NOT EXISTS)? ([a-z_]+)',sql,re.I));rls=set(re.findall(r'ALTER TABLE ([a-z_]+) ENABLE ROW LEVEL SECURITY',sql,re.I));check('Postgres table RLS coverage',not(tables-rls),sorted(tables-rls))
check('No checkpoint DDL',not any('checkpoint' in p.name for p in (R/'spec/sql').glob('*.sql')),'Plain workflow migration only')
check('Original references preserved',all((R/'references'/x).is_file() for x in ['legacy-backend.zip','original-brand-assets.zip','AI-Collaboration-Field-Guide.pdf']),'3 references')
(R/'spec/kit-validation.json').write_text(json.dumps(checks,indent=2)+'\n')
raise SystemExit(0 if all(x['passed'] for x in checks) else 1)
