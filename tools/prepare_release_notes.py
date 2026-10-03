# SPDX-License-Identifier: GPL-3.0-only
"""Generate release notes for the functional ARM64 VRBox/Cardboard APK & VrFocus port."""
import argparse
import json
from pathlib import Path


def generate(build_dir):
    root = Path(build_dir)
    report = json.loads((root / 'build-report.json').read_text())
    apk = report['apk']
    aar = report['aar']
    sums = (root / 'SHA256SUMS.txt').read_text().strip()
    lines = [
        '# MetaPort Horizon OS v2.7 — Functional ARM64 VRBox/Cardboard APK & VrFocus Service Port',
        '',
        '**Créditos e Atribuição Legal:**',
        '- **Meta Horizon OS v2.7 — Meta Platforms, Inc.**',
        '- Port autorizado do sistema Meta Horizon OS (Quest 3 Firmware Build `52168470052900520`) '
        'para smartphones Android ARM64 em headsets VRBox / Google Cardboard.',
        '- Todos os avisos de direitos autorais e atribuições originais da Meta Platforms, Inc. '
        'foram integralmente preservados (`NOTICE.md`, `LICENSE`, `handtracking/distribution/THIRD-PARTY-NOTICE.md`).',
        '',
        '---',
        '',
        '## Pacotes Disponíveis nesta Release',
        '',
        '1. **`MetaPort-HorizonOS-v2.7-Cardboard-Runtime-arm64.apk`**',
        '   - **Pacote Android:** `org.metaport.horizonos` (`v2.7.0-metaport`, `minSdk 29` Android 10 .. '
        '`targetSdk 35` Android 15, ABI `arm64-v8a`, alinhamento ELF de 16 KiB)',
        f"   - **Tamanho:** `{apk['size_bytes']}` bytes",
        f"   - **SHA-256:** `{apk['sha256']}`",
        '   - **Funcionalidades Integradas:**',
        '     - **Renderizador Estereoscópico OpenGL ES Left/Right Eye (`StereoCardboardView`)** para headsets '
        'VRBox / Google Cardboard com ajuste em tempo real de **IPD** (`54..72 mm`, padrão `63 mm`), '
        '**FOV** (`80°..110°`, padrão `90°`), vinheta óptica e alternância **Stereo VRBox / Mono**.',
        '     - **Rastreamento 3DoF IMU de 100 Hz via NDK (`NativeSensors`)** usando `ASensorEventQueue` '
        '(`GAME_ROTATION_VECTOR`, giroscópio e acelerômetro) com botão de **Recenter** instantâneo e '
        'suporte opcional a **ARCore 6DoF & Câmera (`ArCoreTracking`)**.',
        '     - **Serviço Nativo `vrfocus` Reconstruído (`VrFocusService` `0x29210..0x2dd60` + `libmetaport_adapters.so`)** '
        'pré-publicado em `ServiceDirectory("vrfocus")` antes de `Application.onCreate()` '
        '(resolvendo o bloqueio construtor `ShellApplication.<init>(:153)`), implementando todas as '
        '11 transações Binder de `oculus.internal.IVrFocusService` (`FocusPolicyCore` `0x25460`, '
        '`ClientMetadataCache` `0x10aa0..0x13400`, `DisplayTrackingAccessState` `0x15480..0x2dd60`, '
        '`SessionState` e `WindowObservation`).',
        '     - **Painéis Espaciais 3D do Horizon OS (`VrShell` Home, `LibraryPanelApp`, `SystemUX` Quick Settings, '
        '`VRBox Optics`, `vrfocus & JNI`, `Hands & ARCore`, `Bridge & Legal`)** controlados por '
        '**Head Gaze + Dwell (1.2s)**, **Botões Físicos de Volume (+/-)**, **Touchscreen**, '
        '**Mouse/Teclado** ou **Controles Bluetooth Joy-Con (`JoyConInput`)**.',
        '     - **Ponte Direta para `com.oculus.vrshell`**: detecta automaticamente o pacote original '
        '`VrShell` no dispositivo e permite acioná-lo diretamente.',
        '',
        '2. **`metaport-android-adapters-arm64.aar`**',
        '   - Biblioteca Android ARM64 contendo `jni/arm64-v8a/libmetaport_adapters.so` '
        '(16 KiB ELF page-aligned) e todas as classes de compatibilidade `org.metaport.port.**`.',
        f"   - **Tamanho:** `{aar['size_bytes']}` bytes | **SHA-256:** `{aar['sha256']}`",
        '',
        '3. **`metaport-handtracking-sources.zip`**',
        '   - Pacote auditável de código-fonte, contratos JNI (`shell_jni_contract.hpp`, 76 métodos nativos '
        'de `libshell.so`), kernels C++/NEON de hand tracking (`hand_palette`, `hand_material`, '
        '`hand_arena_layout`, `hand_u8_reduce`, `hand_saturating_pack`, `hand_fmq_mapping`), '
        '`space_data` (`0x55`/`0xcb`) e evidências estáticas verificadas do build `52168470052900520`.',
        '',
        '---',
        '',
        '## Instruções de Instalação (Infinix GT30 Pro X6873 / Smartphones Android ARM64)',
        '',
        '### 1. Instalação Padrão (Sem Root)',
        '1. Baixe `MetaPort-HorizonOS-v2.7-Cardboard-Runtime-arm64.apk` no smartphone Android ARM64 '
        '(Android 10 / API 29 ou superior).',
        '2. Instale o APK normalmente ou via ADB:',
        '   ```sh',
        '   adb install -r MetaPort-HorizonOS-v2.7-Cardboard-Runtime-arm64.apk',
        '   ```',
        '3. Abra **MetaPort official demo by ahambolota** e insira o aparelho no headset **VRBox / Cardboard**.',
        '',
        '### 2. Controles no VRBox / Cardboard e na Tela',
        '- **Head Gaze + Dwell (1.2s):** Olhe para qualquer botão da dock 3D inferior por 1,2 segundo '
        'para alternar o painel espacial sem tocar na tela.',
        '- **Volume + (Hardware):** Avança para o próximo painel espacial do Horizon OS.',
        '- **Volume - (Hardware):** Executa a ação principal do painel atual ou recentraliza a pose (`Recenter`).',
        '- **Touchscreen / Mouse / Joy-Con:** Barra rápida inferior com botões diretos para `Recenter`, '
        '`Stereo/Mono`, `IPD +2mm`, `FOV +5°` e `Action`.',
        '',
        '### 3. Permissões Opcionais via ADB / Shizuku',
        '```sh',
        'adb shell pm grant org.metaport.horizonos android.permission.CAMERA',
        '```',
        '',
        '---',
        '',
        '## Checksums (`SHA256SUMS.txt`)',
        '```text',
        sums,
        '```',
        '',
    ]
    out = root / 'RELEASE-NOTES.md'
    out.write_text('\n'.join(lines))
    return out


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-dir', default='local-analysis/android-build')
    args = parser.parse_args()
    generate(args.build_dir)
