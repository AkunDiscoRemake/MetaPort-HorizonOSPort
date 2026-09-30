"""Run a bounded native *metadata* verifier, never the ExecuTorch runtime."""
import argparse
import hashlib
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
                if path.stat().st_size>64*1024*1024: raise ValueError('Decoded model byte limit')
                row['decoded_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
                if row['decoded_sha256']!=model['decoded_sha256']: raise ValueError('Decoded model hash mismatch')
                run=subprocess.run([str(probe.resolve()),str(path)],capture_output=True,text=True,timeout=45,check=True)
                if len(run.stdout)>16384: raise ValueError('Native report size limit')
                row.update(json.loads(run.stdout))
                row['scalar_crosschecks']=[]
                plans=model.get('schema_candidate',{}).get('execution_plans',[])
                for name,value in row['int_getters'].items():
                    matches=[p for p in plans if p['name']==name and len(p['outputs'])==1]
                    strict=matches[0]['outputs'][0] if len(matches)==1 else {}
                    if strict.get('kind')=='Int':
                        status='AGREEMENT' if strict['serialized_value']==value else 'DISAGREEMENT'
                    elif strict.get('kind')=='SCALAR_LAYOUT_UNRESOLVED':
                        status='NATIVE_INT64_WITH_STRICT_EXTENT_WARNING'
                    else: status='STRICT_READER_NOT_COMPARABLE'
                    row['scalar_crosschecks'].append({'method':name,'native_int64':value,'status':status})
                row['status']='COMPARISON_COMPLETE'
            except (ValueError,OSError,subprocess.SubprocessError) as error:
                row.update(status='COMPARISON_FAILED',error=str(error)[:300])
        result['models'].append(row)
    (directory/'reference-schema-report.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--probe',required=True,type=Path);p.add_argument('--directory',required=True,type=Path)
    args=p.parse_args();result=compare(args.probe,args.directory)
    if any(r['status']!='COMPARISON_COMPLETE' for r in result['models']):
        raise SystemExit('Some native comparisons failed; see report')
