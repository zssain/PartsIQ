#!/usr/bin/env python3
"""Validate build-kit structure and cross references, not future application correctness."""
import ast,hashlib,json,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def read_json(p):return json.loads((ROOT/p).read_text())
def main():
 errors=[];checks=[]
 def check(name,ok,detail):
  checks.append({'check':name,'result':'PASS' if ok else 'FAIL','detail':detail})
  if not ok:errors.append(name+': '+detail)
 fs=read_json('spec/features.json');ps=read_json('spec/prompts.json');order=read_json('spec/execution-order.json');own=read_json('spec/file-ownership.json');pos={x:i for i,x in enumerate(order)}
 check('69 sequential features',[f['id'] for f in fs]==[f'F{i:02}' for i in range(1,70)],str(len(fs)))
 required=['GOAL','READ FIRST','PLAN CHECK','PACKAGES','FILES TO CREATE','FILES TO MODIFY','HOW IT CONNECTS','CONSTRAINTS FOR THIS STEP','ACCEPTANCE TESTS','MANUAL VERIFICATION','DOC UPDATES','ROLLBACK','COMMIT','DONE WHEN']
 prompt_files=list((ROOT/'prompts').glob('[0-9][0-9]-*.md'))+list((ROOT/'prompts').glob('F[0-9][0-9]-*.md'))
 check('97 prompt files',len(prompt_files)==97,str(len(prompt_files)))
 bad=[]
 for p in prompt_files:
  headings=re.findall(r'^## (.+)$',p.read_text(),re.M)
  if headings!=required:bad.append(str(p.relative_to(ROOT)))
 check('Exact prompt template headings',not bad,str(bad))
 bad=[]
 for f in fs:
  for key in ['trace','prompt']:
   if not (ROOT/f[key]).is_file():bad.append(f[key])
  if f['test'] not in own:bad.append(f['test'])
 check('Feature prompt trace test coverage',not bad,str(bad))
 bad=[]
 for id,p in ps.items():
  for dep in p['deps']:
   if dep not in pos or pos[dep]>=pos[id]:bad.append(id+'->'+dep)
  for path in p['modifies']:
   if path not in own or pos[own[path]['creator']]>=pos[id]:bad.append(id+' modifies '+path)
 check('No forward manifest dependencies',not bad,str(bad))
 bad=[]
 for path,v in own.items():
  if v['creator'] not in ps:bad.append(path)
  elif v['kind']!='legacy' and path not in ps[v['creator']]['creates']:bad.append(path)
 check('One creator per planned file',not bad,str(bad))
 pins=read_json('spec/dependency-receipts.json');bad=[p['package'] for p in pins if not p.get('eligible') or p.get('error') or p['released'][:10]>'2026-09-26' or p.get('installed_by') not in ps]
 check('Direct package release eligibility and owner',not bad,str(bad))
 sql='\n'.join(p.read_text() for p in (ROOT/'spec/sql').glob('00[1-5]*.sql'))
 tables=re.findall(r'CREATE TABLE (\w+)\s*\(',sql,re.I)
 missing=[t for t in tables if f'ALTER TABLE {t} ENABLE ROW LEVEL SECURITY' not in sql]
 check('Application tables have explicit RLS',not missing,str(len(tables))+' tables; missing '+str(missing))
 check('Critical legacy constraints preserved',all(x in sql for x in ['EXCLUDE USING gist','prevent_supersession_cycle','audit_log_no_truncate','messages_publication_guard','candidate_item_fk']), 'serial overlap,cycles,audit,publication,item correlation')
 bad=[]
 for a in read_json('brand/assets-manifest.json'):
  p=ROOT/a['path']
  if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=a['sha256']:bad.append(a['path'])
 check('Brand asset hashes',not bad,str(bad))
 bad=[]
 _skip_dirs={'.venv','venv','node_modules','.git','__pycache__','.next'}
 for p in ROOT.rglob('*.md'):
  if _skip_dirs.intersection(p.relative_to(ROOT).parts):continue  # uncommitted build artifacts, not authored kit docs
  if any(token in p.read_text() for token in ['TODO','...','similar to above']):bad.append(str(p.relative_to(ROOT)))
 check('No unfinished prose markers',not bad,str(bad))
 for p in [ROOT/'spec/contracts.py',ROOT/'tools/kit/verify_kit.py']:
  try:ast.parse(p.read_text())
  except SyntaxError as e:errors.append(str(e))
 report={'scope':'Build-kit structural validation only; no application or deployment tests executed','checks':checks,'errors':errors}
 (ROOT/'spec/kit-validation.json').write_text(json.dumps(report,indent=2)+'\n')
 for c in checks:print(c['result'],c['check'],c['detail'])
 print('KIT VALIDATION '+('FAILED' if errors else 'PASSED'))
 return 1 if errors else 0
if __name__=='__main__':sys.exit(main())
