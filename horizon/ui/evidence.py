# SPDX-License-Identifier: GPL-3.0-only
"""Bounded original UI/UX call-site and resource evidence, never a replacement UI."""
import hashlib
from pathlib import Path
import re

CATEGORIES = {
    'cloud_identity': r'OAuth|access_token|refresh_token|AccountManager|IdentityManagement|DeviceAuth',
    'cloud_store_entitlements': r'entitlement|purchase|billing|StoreService|PackageInstaller|OCMS',
    'settings_capabilities': r'DeviceConfig|Settings\.(?:Secure|Global|System)|setComponentEnabledSetting|setSystemProperty',
    'depth_runtime': r'DepthImage|DepthSensor|depthMap|depthTexture|environmentDepth|depthEstimat',
    'passthrough': r'passthrough(?!ShellCommand|HierarchyChangeListener)|seeThrough|environmentBlend',
    'composition': r'SurfaceControl|SurfaceTexture|SurfaceView|TextureView|EGL|Compositor|setLayer|swapchain',
    'panels_navigation': r'PanelManager|PanelService|ShellCommand|launchPanel|showPanel|navigation|backStack',
    'ux_animation': r'propertyName|interpolator|<set\b|<alpha\b|<translate\b|ObjectAnimator|ValueAnimator|AnimatorSet|TransitionManager|SpringAnimation|Choreographer',
    'input_hands': r'hand.?track|onHand|nativeJoypadAxis|IInputDataInjection|nativeKeyEvent',
    'privileged_services': r'ServiceManager|getService\(|bindService\(|enforceCallingPermission|checkCallingPermission',
}
PATTERNS = {k: re.compile(v, re.I) for k, v in CATEGORIES.items()}
LIMIT = 48


def summarize_ux(root):
    root = Path(root)
    result = {'ui_ported': False, 'runtime_validated': False,
              'scope': 'Bounded lexical candidates, not resolved call graph or complete UI recovery',
              'categories': {k: {'matching_lines': 0, 'sites': [], 'truncated': False} for k in PATTERNS},
              'resource_files': [], 'resource_files_total': 0,
              'skipped_oversized_files': [], 'source_coverage_complete': True}
    files = sorted(root.rglob('*'))
    if len(files) > 150000:
        raise ValueError('Generated file count limit')
    files.sort(key=lambda p: (p.name in ('R.java', 'BuildConfig.java'), 0 if '/com/oculus/' in str(p) or '/com/meta/' in str(p) else 1, str(p)))
    for path in files:
        if not path.is_file() or path.is_symlink():
            continue
        if path.suffix not in ('.java', '.xml'):
            continue
        if path.stat().st_size > 4 * 1024 * 1024:
            result['skipped_oversized_files'].append({'path':path.relative_to(root).as_posix(),
                                                    'size_bytes':path.stat().st_size})
            result['source_coverage_complete'] = False
            continue
        raw = path.read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        relative = path.relative_to(root).as_posix()
        if path.suffix == '.xml':
            result['resource_files_total'] += 1
            if len(result['resource_files']) < 160:
                result['resource_files'].append({'path': relative, 'sha256': sha, 'size_bytes': len(raw)})
        text = raw.decode('utf-8', errors='replace')
        lines = text.splitlines()
        failed = bool(re.search(r'JADX ERROR|Method not decompiled:', text))
        for number, line in enumerate(lines):
            for category, pattern in PATTERNS.items():
                if not pattern.search(line):
                    continue
                bucket = result['categories'][category]
                bucket['matching_lines'] += 1
                if len(bucket['sites']) >= LIMIT:
                    bucket['truncated'] = True
                    continue
                start = max(0, number - 5)
                bucket['sites'].append({'path': relative, 'line': number + 1,
                    'start_line': start + 1, 'generated_sha256': sha,
                    'has_decompiler_errors': failed,
                    'context': '\n'.join(x[:1200] for x in lines[start:number + 6])})
    result['resource_inventory_truncated'] = result['resource_files_total'] > len(result['resource_files'])
    return result
