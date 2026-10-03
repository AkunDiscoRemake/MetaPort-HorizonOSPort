# SPDX-License-Identifier: GPL-3.0-only
"""Bounded project syntax/unit/source-bundle checks, with explicit machine-readable scope."""
import argparse
import ast
import json
from pathlib import Path
import subprocess
import sys
import re
import tempfile
import time
import zipfile

ROOT=Path(__file__).resolve().parents[1]
SUITES=('tests','guest/tests','handtracking/ai/tests','horizon/ui/tests','horizon/depth/tests')
CHILD='''import json,sys,unittest
suite=unittest.defaultTestLoader.discover(sys.argv[1])
r=unittest.TextTestRunner(verbosity=2).run(suite)
with open(sys.argv[2],'w') as f:json.dump({'tests':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skipped':len(r.skipped),'successful':r.wasSuccessful()},f)
sys.exit(not r.wasSuccessful())
'''


def run(output):
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=True)
    records=[]
    def command(name,args,cwd=ROOT):
        log=output/(name+'.log');record={'name':name,'command':args,'cwd':str(cwd)}
        start=time.monotonic()
        with log.open('w') as stream:
            try:
                result=subprocess.run(args,cwd=cwd,stdout=stream,stderr=subprocess.STDOUT,timeout=240)
                record['exit_code']=result.returncode
            except subprocess.TimeoutExpired:
                record.update(exit_code=124,timed_out=True)
        record['seconds']=round(time.monotonic()-start,3);records.append(record)
        print(name,record['exit_code'],flush=True)
        return record['exit_code']==0
    report={'scope':'Project-owned syntax/unit tests and source-package closure only',
            'original_firmware_executed':False,'physical_device_tested':False,'checks':records}
    try:
        python_files=[]
        for root in ('tools','guest','horizon','handtracking','tests'):
            for path in (ROOT/root).rglob('*.py'):
                ast.parse(path.read_bytes(),filename=str(path));python_files.append(str(path.relative_to(ROOT)))
        report['python_syntax_files']=len(python_files)
        import yaml
        for workflow in sorted((ROOT/'.github/workflows').glob('*.yml')):
            data=yaml.load(workflow.read_text(),Loader=yaml.BaseLoader)
            for job,config in data.get('jobs',{}).items():
                for i,step in enumerate(config.get('steps',[])):
                    if 'run' not in step:continue
                    if step.get('shell','bash')!='bash':
                        raise ValueError('Unsupported script shell: '+str(workflow))
                    script=re.sub(r"\$\{\{.*?\}\}",'EXPRESSION_VALUE',step['run'],flags=re.S)
                    with tempfile.NamedTemporaryFile(mode='w',suffix='.sh',dir=output) as f:
                        f.write(script);f.flush()
                        command(f'workflow-{workflow.stem}-{job}-{i}',['bash','-n',f.name])
        for path in (ROOT/'tools').glob('*.sh'):
            command('shell-'+path.stem,['bash','-n',str(path)])
        command('generated-jni',[sys.executable,'-m','horizon.ui.generate_jni_contract','--check'])
        for i,suite in enumerate(SUITES):
            command('suite-'+str(i),[sys.executable,'-c',CHILD,suite,str(output/f'suite-{i}.json')])
        archive=output/'source-closure.zip'
        if command('source-package',[sys.executable,'-m','handtracking.distribution.package','--output',str(archive)]):
            from handtracking.distribution.package import verify
            verify(archive) # Validates paths, sizes, duplicates and every hash before extracting.
            with tempfile.TemporaryDirectory(dir=output,prefix='source-closure-') as d:
                with zipfile.ZipFile(archive) as z:z.extractall(d)
                for i,suite in enumerate(('handtracking/ai/tests','horizon/ui/tests')):
                    command('package-suite-'+str(i),[sys.executable,'-c',CHILD,suite,str(output/f'package-suite-{i}.json')],Path(d))
        report['passed']=all(r['exit_code']==0 for r in records)
    except Exception as error:
        report.update(passed=False,error=repr(error))
    finally:
        report['source_commit']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
        (output/'project-checks.json').write_text(json.dumps(report,indent=2)+'\n')
    return report['passed']

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',default='local-analysis/project-checks')
    args=parser.parse_args()
    # Keep source-bundle subprocess imports independent from the checkout. A caller
    # using --target dependencies must provide an absolute PYTHONPATH to those deps.
    sys.exit(0 if run(args.output) else 1)
