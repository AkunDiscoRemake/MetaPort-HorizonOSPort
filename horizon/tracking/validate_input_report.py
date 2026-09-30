# SPDX-License-Identifier: GPL-3.0-only
"""Validate bounded static hand evidence, not private ABI/runtime correctness."""
import argparse
import json
from pathlib import Path
from horizon.tracking.prepare_input import ENGINE_SHA


def validate(report):
    if report.get('program_sha256','').lower()!=ENGINE_SHA:
        raise ValueError('Wrong engine report')
    if report.get('firmware_executed') is not False or report.get('abi_validated') is not False:
        raise ValueError('Unexpected runtime/ABI claim')
    functions=report.get('functions',[])
    if not 3<=len(functions)<=32:raise ValueError('Function evidence count')
    addresses=[f['elf_address'] for f in functions]
    if len(set(addresses))!=len(addresses):raise ValueError('Duplicate selected function')
    recovered={f['elf_address'] for f in functions if f.get('status')=='DECOMPILED_NOT_VALIDATED' and f.get('c_like')}
    if not {0x1620ce0,0x16222a0,0x162bee0}<=recovered:
        raise ValueError('Missing constructor or executor evidence')
    windows=report.get('pointer_windows',[])
    if not 1<=len(windows)<=24:raise ValueError('Pointer evidence count')
    candidates={w.get('candidate_function') for w in windows if w.get('candidate_abi_validated') is False}
    matched=[f['name'] for f in functions if f.get('name') in candidates and
             f.get('status')=='DECOMPILED_NOT_VALIDATED' and f.get('c_like')]
    if not matched:raise ValueError('No pointer candidate decompiled')
    return {'qualification':'STATIC_EVIDENCE_ACCEPTED_NOT_RUNTIME_VALIDATED',
            'selected_functions':len(functions),'decompiled_pointer_candidates':len(matched),
            'private_abi_validated':False}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('report',type=Path)
    a=p.parse_args();print(json.dumps(validate(json.loads(a.report.read_text())),indent=2))
