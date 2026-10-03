# SPDX-License-Identifier: GPL-3.0-only
"""Select hand/tracking task-profile definitions; never apply privileges or CPU policy."""
import re


def select_profiles(root, extra_roots=()):
    if not isinstance(extra_roots,(tuple,list)) or len(extra_roots)>2048 or not all(isinstance(x,str) and x for x in extra_roots):
        raise ValueError("Invalid explicit profile roots")
    if not isinstance(root,dict): raise ValueError('Profile root must be an object')
    definitions={};duplicates=[];kinds={}
    for kind in ('Profiles','AggregateProfiles'):
        rows=root.get(kind,[])
        if not isinstance(rows,list) or len(rows)>2048: raise ValueError('Profile array limit')
        for row in rows:
            if not isinstance(row,dict) or not isinstance(row.get('Name'),str): raise ValueError('Profile name')
            name=row['Name']
            if name in definitions: duplicates.append(name)
            else: definitions[name]=row;kinds[name]=kind
    if duplicates: raise ValueError('Ambiguous profile names')
    pending=[name for name in definitions if re.search(r'hand|tracking',name,re.I)] + list(extra_roots)
    selected={};missing=set()
    while pending:
        name=pending.pop()
        if name in selected or name in missing: continue
        if name not in definitions: missing.add(name);continue
        selected[name]=definitions[name]
        if kinds[name]=='AggregateProfiles':
            children=definitions[name].get('Profiles',[])
            if not isinstance(children,list) or len(children)>2048 or not all(isinstance(x,str) for x in children):
                raise ValueError('Aggregate profile references')
            pending.extend(children)
    attributes=root.get('Attributes',[])
    if not isinstance(attributes,list) or len(attributes)>2048: raise ValueError('Attribute limit')
    names=set()
    for profile in selected.values():
        actions=profile.get('Actions',[])
        if not isinstance(actions,list) or len(actions)>2048: raise ValueError('Action limit')
        for action in actions:
            if isinstance(action,dict) and action.get('Name')=='SetAttribute':
                params=action.get('Params',{})
                if isinstance(params,dict) and isinstance(params.get('Name'),str):names.add(params['Name'])
    attrs=[a for a in attributes if isinstance(a,dict) and a.get('Name') in names]
    return {'explicit_profile_roots':sorted(set(extra_roots)),'definitions':selected,'referenced_attributes':attrs,'unresolved_profile_names':sorted(missing),
            'unresolved_attribute_names':sorted(names-{a['Name'] for a in attrs}),
            'runtime_applied':False,'phone_compatible':False,
            'scope':'Single-file profile and aggregate definitions; cross-file precedence and privileged application not validated'}
