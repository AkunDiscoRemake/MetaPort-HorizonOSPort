"""Exact guest block-node labels using existing original SELinux types only.

No allow rules, policy binary changes, permissive domains or blanket relabeling.
The generated text is an explicit runtime overlay, not an original firmware file.
"""
import re

ORIGINAL='/dev/block/platform/soc/1d84000.ufshc/by-name/'


def adapt(original,parts):
    rules=[]
    for number,part in enumerate(parts,1):
        matches=[]
        for line in original.splitlines():
            fields=line.split()
            if len(fields)==2 and fields[0].startswith(ORIGINAL):
                if re.fullmatch(fields[0],ORIGINAL+part['name']):matches.append(fields[1])
        if len(set(matches))!=1:raise ValueError('Ambiguous/missing original label for '+part['name'])
        context=matches[0]
        if not re.fullmatch(r'u:object_r:[a-z0-9_]+:s0',context):raise ValueError('Unsupported context')
        rules.append({'node':f'/dev/block/vda{number}','partition':part['name'],'context':context})
    overlay=original.rstrip()+'\n\n# MetaPort: exact nodes of the prepared disposable virtio disk\n'
    overlay+=''.join(r['node']+' '+r['context']+'\n' for r in rules)
    return overlay,rules
