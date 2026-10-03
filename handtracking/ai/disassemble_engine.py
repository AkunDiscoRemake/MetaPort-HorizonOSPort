# SPDX-License-Identifier: GPL-3.0-only
"""All executable-section assembly of the pinned tracking engine, not working AI."""
import argparse
import json
from pathlib import Path
from handtracking.ai.prepare_input import ENGINE_SHA
from tools.disassemble_original_arm64 import disassemble_verified

ENGINE_SIZE=41154352


def run(library,output):
    output=Path(output)
    report=disassemble_verified(library,output/'libtrackingengines-executable-sections.asm.gz',
                               ENGINE_SHA,ENGINE_SIZE)
    report.update(quest_hand_inference_executed=False,all_hand_ai_disassembled=False)
    (output/'hand-engine-full-disassembly.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--library',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();run(a.library,a.output)
