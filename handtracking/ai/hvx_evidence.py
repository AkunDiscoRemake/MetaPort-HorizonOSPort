# SPDX-License-Identifier: GPL-3.0-only
"""Bounded HVX operand-form/context evidence, NOT lifted kernels or semantic equivalence."""
from collections import defaultdict, deque
import re

FAMILIES={
    'multiply_reduce':{'vrmpy','vdmpy','vmpy','vmpye','vmpyo','vmpyie','vmpyio','vmpa'},
    'lookup':{'vlut16','vlut32'},
    'repacking':{'vdelta','vrdelta','vshuff','vdeal','valign','vlalign'},
    'narrow_saturate':{'vpack','vsat','vasr','vunpack'},
    'gather_scatter':{'vgather','vscatter'},
}


def operand_form(line):
    body=line.split(':',1)[1].strip().strip('{} ').strip()
    # Only classify textual operand shapes. Erasing register numbers loses
    # aliasing/dependency information: this is NOT a kernel equivalence test.
    return re.sub(r'\b([vrq])\d+(?::\d+)?',
                  lambda m:m[1]+('Pair' if ':' in m[0] else 'N'),body)


class HvxEvidence:
    def __init__(self):
        self.forms=defaultdict(dict);self.dropped=defaultdict(int)
        self.previous=deque(maxlen=8);self.pending=[];self.windows=[]
        self.family_counts=defaultdict(int)

    def feed(self,line):
        if not re.match(r'^\s*[0-9a-fA-F]+:',line): return
        for window in self.pending:
            window['listing'].append(line[:1024]);window['following_lines']+=1
        self.pending=[w for w in self.pending if w['following_lines']<8]
        if re.search(r'\bv\d+',line):
            ops=set(re.findall(r'\b(v[a-z][a-z0-9_]*)\s*\(',line));shape=operand_form(line)
            for op in sorted(ops):
                if op in self.forms and shape in self.forms[op]:
                    self.forms[op][shape]['listing_line_occurrences']+=1
                elif len(self.forms[op])<16:
                    self.forms[op][shape]={'listing_line_occurrences':1,'example':line[:1024]}
                else: self.dropped[op]+=1
            for family,opcodes in FAMILIES.items():
                if ops & opcodes and self.family_counts[family]<2:
                    window={'family':family,'center_listing':line[:1024],
                            'preceding_lines':len(self.previous),'following_lines':0,
                            'listing':list(self.previous)+[line[:1024]]}
                    self.windows.append(window);self.pending.append(window);self.family_counts[family]+=1
        self.previous.append(line[:1024])

    def report(self):
        windows=[]
        for window in self.windows:
            windows.append(dict(window,context_truncated=window['preceding_lines']<8 or window['following_lines']<8))
        return {'operand_forms':dict(self.forms),'unretained_form_occurrences':dict(self.dropped),
                'instruction_windows':windows,'hand_kernel_identified':False,
                'scope':'16 textual forms/opcode; 2 neighborhoods/family, +/-8 listing lines; not function boundaries or runtime activation'}
