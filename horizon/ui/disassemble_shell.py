# SPDX-License-Identifier: GPL-3.0-only
"""Disassemble executable sections of the fixed original libshell; not runtime proof."""
import argparse
import json
from pathlib import Path
from horizon.ui.prepare_shell import POLICY
from tools.disassemble_original_arm64 import stream_listing, disassemble_verified


def run(library,output):
    output=Path(output);policy=json.loads(POLICY.read_text())
    report=disassemble_verified(library,output/'libshell-executable-sections.asm.gz',
                               policy['library_sha256'],policy['library_size_bytes'])
    (output/'shell-full-disassembly.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--library',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();run(a.library,a.output)
