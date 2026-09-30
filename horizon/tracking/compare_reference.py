"""Run a bounded native *metadata* verifier, never the ExecuTorch runtime."""
import argparse
import json
from pathlib import Path
import subprocess

SCHEMA_COMMIT='4b9d44206a99c1ce39315487599971b257a02ed8'


def compare(probe,directory):
    report=json.loads((directory/'ptez-report.json').read_text())
    result={'status':'INDEPENDENT_PUBLIC_SCHEMA_COMPARISON_NOT_RUNTIME_VALIDATION',
        'schema_commit':SCHEMA_COMMIT,
        'flatc_version':subprocess.check_output(['flatc','--version'],text=True).strip(),
        'model_executed':False,'models':[]}
    for model in report['models']:
        path=directory/(Path(model['path']).stem+'.pte')
        row={'path':model['path']}
        if not path.is_file():
            row['status']='NO_DECODED_MODEL'
        else:
            try:
                run=subprocess.run([str(probe.resolve()),str(path)],capture_output=True,text=True,timeout=45,check=True)
                if len(run.stdout)>16384: raise ValueError('Native report size limit')
                row.update(json.loads(run.stdout))
                row['status']='COMPARISON_COMPLETE'
            except (ValueError,subprocess.SubprocessError) as error:
                row.update(status='COMPARISON_FAILED',error=str(error)[:300])
        result['models'].append(row)
    (directory/'reference-schema-report.json').write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--probe',required=True,type=Path);p.add_argument('--directory',required=True,type=Path)
    args=p.parse_args();compare(args.probe,args.directory)
