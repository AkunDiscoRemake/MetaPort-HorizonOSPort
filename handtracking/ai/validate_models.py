# SPDX-License-Identifier: GPL-3.0-only
"""Fail CI on incomplete fixed-corpus evidence, not on phone/root/VR status.

A successful offline analysis is explicitly NOT runtime/ABI/inference validation.
No firmware, models, delegates or device commands are executed by this module.
"""
import argparse
import json
import math
from pathlib import Path
from handtracking.ai.compare_reference import SCHEMA_COMMIT

POLICY=Path(__file__).with_name('model-evidence-policy.json')


def require(condition,message):
    if not condition: raise ValueError(message)


def indexed(rows,key):
    require(isinstance(rows,list) and len(rows)<=128,'Invalid row count/type')
    result={}
    for row in rows:
        name=row[key]
        require(name not in result,'Duplicate '+key+': '+name)
        result[name]=row
    return result


def validate(models,reference):
    policy=json.loads(POLICY.read_text())
    require(models['build']==policy['build'],'Wrong firmware build')
    require(models['models_executed'] is False and reference['model_executed'] is False,
            'Offline evidence must not claim model execution')
    require(reference['schema_commit']==SCHEMA_COMMIT,'Unexpected public reference schema')
    original=indexed(models['models'],'path');native=indexed(reference['models'],'path')
    require(set(original)==set(native)==set(policy['models']),'Missing/unexpected model')
    scalar_count=0;warnings=0
    for path,pinned in policy['models'].items():
        model=original[path];other=native[path]
        require(model['status']=='DECOMPRESSED_STRUCTURAL_ONLY',path+': decompression incomplete')
        require(model['firmware_executed'] is False and model['inference_tested'] is False,
                path+': unexpected runtime claim')
        for key in ('source_sha256','decoded_sha256'):
            require(model[key]==pinned[key],path+': model digest mismatch')
        require(other['decoded_sha256']==pinned['decoded_sha256'],path+': native digest mismatch')
        require(other['status']=='COMPARISON_COMPLETE' and other['public_schema_verifier_passed'] is True,
                path+': native verification failed')
        require(other['model_executed'] is False,path+': unexpected execution claim')
        schema=model['schema_candidate']
        require(schema['interpretation']=='PUBLIC_SCHEMA_CANDIDATE_NOT_RUNTIME_VALIDATED',path+': missing schema qualification')
        require(schema['camera_semantics_recovered'] is False,path+': camera semantics not measured')
        plans=indexed(schema['execution_plans'],'name');forward=plans['forward']
        require(forward['control_flow_evaluated'] is False,path+': control flow not evaluated')
        calls=forward['delegate_call_sites'];dpe='/dpe/' in path
        require(len(calls)==(2 if dpe else 1) and all(c['backend']=='HexagonRpcBackend' for c in calls),
                path+': delegate-call evidence changed')
        expected={} if dpe else ({'num_layers':5,'kernel_size':7,'hidden_dim':384,
                  'left_context':80 if 'SKBV32' in path else 60,'featurizer_version':4}
                  if '/surface_keyboard/' in path else
                  {'num_layers':6,'kernel_size':16,'hidden_dim':128,'left_context':31})
        require(other['int_getters']==expected,path+': native getter constants changed')
        checks=indexed(other['scalar_crosschecks'],'method')
        require(set(checks)==set(expected),path+': incomplete scalar crosschecks')
        for name,value in expected.items():
            check=checks[name]
            require(type(check['native_int64']) is int and check['native_int64']==value,path+': scalar mismatch')
            require(check['status'] in ('AGREEMENT','NATIVE_INT64_WITH_STRICT_EXTENT_WARNING'),path+': reader disagreement')
            warning=check['status']=='NATIVE_INT64_WITH_STRICT_EXTENT_WARNING'
            strict=plans[name]['outputs']
            require(len(strict)==1,path+': getter output changed')
            require(strict[0]['kind']==('SCALAR_LAYOUT_UNRESOLVED' if warning else 'Int'),path+': crosscheck inconsistent')
            if not warning:require(strict[0]['serialized_value']==value,path+': strict value mismatch')
            warnings+=warning;scalar_count+=1
        if dpe:
            attributes=model['serialized_attributes']
            require(attributes['status']=='SERIALIZED_ATTRIBUTES_RECOVERED',path+': missing attributes')
            evidence=attributes['evidence'];fields=attributes['attributes']
            require(evidence['sha256']==pinned['attributes_sha256'] and evidence['bytes']==1366,
                    path+': attributes digest/length changed')
            require(evidence['getter_executed'] is False and evidence['instruction_count']==0,
                    path+': attributes not a serialized constant')
            require(fields['image_size']==[96,96] and fields['use_uint8_input'] is False and fields['input_format']=='v2',
                    path+': frontend contract changed')
            scales=fields['sigma_scales']
            require(set(scales)=={'MixedV_GT_SKEL','SingleV_GT_SKEL','MultiV_GT_SKEL',
                    'MultiV_Use_PredS','MixedV_Use_PredS','SingleV_Use_PredS'},path+': sigma keys changed')
            require(all(len(v)==22 and all(type(x) in (int,float) and math.isfinite(x) for x in v)
                        for v in scales.values()),path+': invalid sigma metadata')
            image=forward['inputs'][0]
            require(image['kind']=='Tensor' and image['scalar_type_code']==0 and image['sizes']==[4,1,96,96],
                    path+': compiled image input changed')
    return {'status':'FIXED_CORPUS_EVIDENCE_ACCEPTED_NOT_RUNTIME_VALIDATED','build':policy['build'],
            'model_count':len(original),'scalar_count':scalar_count,'strict_extent_warnings':warnings,
            'models_executed':False,'camera_conversion_validated':False,'horizon_ported':False}


def load(path):
    require(path.stat().st_size<=8*1024*1024,'JSON report size limit')
    def pairs(items):
        result={}
        for key,value in items:
            require(key not in result,'Duplicate JSON key')
            result[key]=value
        return result
    return json.loads(path.read_text(),object_pairs_hook=pairs)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',required=True,type=Path);args=parser.parse_args()
    args.directory.mkdir(parents=True,exist_ok=True)
    try:
        result=validate(load(args.directory/'ptez-report.json'),load(args.directory/'reference-schema-report.json'))
        code=0
    except (ValueError,KeyError,TypeError,IndexError,OSError) as error:
        result={'status':'EVIDENCE_REJECTED','error':str(error)[:300],'horizon_ported':False};code=1
    (args.directory/'model-evidence-validation.json').write_text(json.dumps(result,indent=2)+'\n')
    return code


if __name__=='__main__':raise SystemExit(main())
