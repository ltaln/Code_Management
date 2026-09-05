"""Adversarial checks on copies; never modifies original model assets."""
from pathlib import Path
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import uuid

ROOT=Path(__file__).resolve().parents[1]
workspace=ROOT / 'runtime' / 'test_runs'
workspace.mkdir(parents=True, exist_ok=True)
cases=workspace / ('verification-' + uuid.uuid4().hex[:8])
assert cases.is_relative_to(workspace)
cases.mkdir()
spec=importlib.util.spec_from_file_location('verify_assets',ROOT/'scripts/verify_assets.py')
v=importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)
base=v.verify(ROOT)
assert base['asset_integrity']=='PASS',base
results=[{'case':'original_assets','passed':True}]

def run_case(name, mutate, expected):
    target=cases/name
    shutil.copytree(ROOT,target,ignore=shutil.ignore_patterns('.git','__pycache__','runtime'))
    mutate(target)
    report=v.verify(target)
    assert report['asset_integrity']=='FAIL' and any(expected in e for e in report['errors']),report
    results.append({'case':name,'passed':True,'detected':expected})

run_case('prompt_tamper',lambda r:(r/'prompts/HH520-PROMPT-V2.1.txt').write_text('modified',encoding='utf-8'),'PROMPT_NOT_VERBATIM')
run_case('missing_model',lambda r:(r/'models/HH520_V2.1-Test/模型说明.md').rename(r/'moved-model.md'),'MISSING_ASSET')
run_case('extra_model',lambda r:(r/'models/new-weights.json').write_text('{}',encoding='utf-8'),'UNLOCKED_ASSET')
run_case('invalid_config_json',lambda r:(r/'config/task.json').write_text('{broken',encoding='utf-8'),'INVALID_JSON')
run_case('broken_local_link',lambda r:(r/'README.md').write_text('[missing](does-not-exist.md)',encoding='utf-8'),'BROKEN_LINK')
def disconnect(r):
    p=r/'config/system.json'
    d=json.loads(p.read_text(encoding='utf-8'));d['gpt_executor']=''
    p.write_text(json.dumps(d),encoding='utf-8')
target=cases/'disconnected_runtime'
shutil.copytree(ROOT,target,ignore=shutil.ignore_patterns('.git','__pycache__','runtime'))
disconnect(target)
disconnected=v.verify(target)
assert disconnected['asset_integrity']=='PASS' and not disconnected['runtime_ready'] and 'RUNTIME_SWITCH_DISABLED' in disconnected['readiness_blockers'],disconnected
results.append({'case':'disconnected_runtime','passed':True,'detected':'RUNTIME_SWITCH_DISABLED'})
run_case('missing_phase',lambda r:(r/'docs/phases/phase_6_backtest.md').rename(r/'moved-phase.md'),'MISSING:')
child_env=dict(os.environ,PYTHONIOENCODING='utf-8')
proc=subprocess.run([sys.executable,str(ROOT/'scripts/verify_assets.py'),'--require-ready'],capture_output=True,text=True,encoding='utf-8',env=child_env)
assert proc.returncode==0,proc
results.append({'case':'readiness_gate','passed':True,'exit_code':0})
proc=subprocess.run([sys.executable,str(ROOT/'scripts/wake.py')],capture_output=True,text=True,encoding='utf-8',env=child_env)
assert proc.returncode==0 and 'HH520-FOOTBALL-AI-V2026' in proc.stdout,proc
results.append({'case':'wake','passed':True})

# Validate standard transport schemas when the optional validator is available.
try:
    import jsonschema
except ModuleNotFoundError:
    for p in ROOT.rglob('*.schema.json'):
        json.loads(p.read_text(encoding='utf-8'))
    results.append({'case':'schema_json_syntax','passed':True,'validator':'not_installed'})
else:
    for p in ROOT.rglob('*.schema.json'):
        doc=json.loads(p.read_text(encoding='utf-8'))
        jsonschema.Draft202012Validator.check_schema(doc)
    schema=json.loads((ROOT/'task_manager/task.schema.json').read_text(encoding='utf-8'))
    example=json.loads((ROOT/'task_manager/example.task.json').read_text(encoding='utf-8'))
    validator=jsonschema.Draft202012Validator(schema,format_checker=jsonschema.FormatChecker())
    validator.validate(example)
    bad=dict(example,date='2026-99-99')
    assert list(validator.iter_errors(bad))
    results.append({'case':'schema_and_task_example','passed':True})
(cases/'verification_results.json').write_text(json.dumps({'asset_report':base,'tests':results},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'tests_passed':len(results),'asset_report':base},ensure_ascii=False,indent=2))
