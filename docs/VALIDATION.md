# Validação: o que cada resultado realmente comprova

**Não há APK Horizon funcional ou versão estável certificada.** Os testes abaixo
não executam o firmware original, não medem desempenho VR e não validam o Infinix.

## Camadas independentes

| Camada | Verificação | Não comprova |
|---|---|---|
| Sintaxe e CI | AST de todos os Python do projeto, `bash -n` dos scripts e passos dos workflows, actionlint fixado em 1.7.7 | Correção semântica dos algoritmos ou runtime Android |
| Regressões Python | OTA/ELF/DEX, guest, mãos, UI, depth, proveniência e formatos | Execução do código original ou inferência |
| Fontes separadas | Construção e verificação de hashes do ZIP; testes de mãos e UI executados numa extração isolada | Runtime independente completo das mãos |
| Nativo host | Nove executáveis com ASan/UBSan; cache e roteador concorrentes também com TSan | Oráculo original, driver, NN/DSP ou ARM64 Android |
| Android ARM64 | NDK, AAR, testes Java, lint, alinhamento ELF de 16 KiB; testes ARM64/QEMU dos helpers no workflow existente | Compatibilidade física, compositor ou pacote METAPORT instalável |
| Android instrumentado | APIs 29 e 35, x86_64 exclusivamente para testes, GPU emulada; biblioteca JNI do projeto realmente carregada | Horizon, GPU MediaTek, ARCore/depth/câmera reais, mãos ou Bluetooth físico |
| Original estático | APK/ELF fixados por hash, DEX e instruções originais, reconstrução C-like com erros preservados | ABI privada completa ou código recompilável fiel |

Não somar essas camadas para inventar uma certificação de ponta a ponta.

## Testes instrumentados

`AdapterRuntimeTest` cobre:

1. Inicialização/parada repetidas de sensores, invalidação de amostras e proteção
   após fechamento; sensores ausentes não são simulados como disponíveis.
2. Criação EGL, consulta de superfície, renderização/leitura de um pixel,
   apresentação e compilação/link dos shaders OES — **sem imagem de câmera**.
3. Fechar uma saída EGL sem invalidar outra ainda aberta.
4. Rejeitar acesso ao renderer em outro contexto/thread e após fechamento;
   um frame de câmera ausente permanece ausente.
5. Ciclo do serviço de entrada na thread principal — **sem afirmar Joy-Con pareado**.

O runner ativa CheckJNI. O relatório exige os nomes exatos dos testes, sem
falhas, skips, duplicações ou casos ausentes; retorno zero do Gradle sozinho não
é suficiente. Os APKs gerados são fixtures internas, sem launcher, e **não são
publicados como produto**. A opção `-PmetaportEmulatorTests=true` desativa a
variante release; ARM64 continua sendo o ABI padrão dos adaptadores.

O run **36814595164** passou nos dois emuladores com os quatro testes iniciais.
O run **36815321281** executou esses quatro sem falhas, mas foi reprovado pelo
verificador: a contagem mínima tinha sido definida incorretamente como cinco.
A cobertura agora é um conjunto explícito de nomes, conferido também contra o
fonte Java, e inclui o quinto teste real de contexto. Não apagar a falha histórica
nem chamá-la de regressão de runtime dos quatro testes executados.

Resultados atuais: `analysis/android-runtime/api-29.json` e `api-35.json` incluem
commit, run, casos individuais e escopo. Consulte `passed` e a execução associada;
a mera existência do arquivo não significa sucesso. Logs/XML ficam nos artifacts.

## Comandos reproduzíveis

```sh
python3 -m pip install -r handtracking/ai/requirements.txt \
  -r horizon/ui/abi-requirements.txt -r tools/check-requirements.txt
python3 -m tools.check_project
python3 -m tools.check_native

gradle -p port/android :adapters:assembleRelease \
  :adapters:testReleaseUnitTest :adapters:lintRelease
# Com emulador já iniciado; NÃO gera uma release x86_64:
bash tools/run_android_runtime.sh
```

Relatórios/logs locais ficam em `local-analysis/`, fora do Git. Os testes
instrumentados têm timeout por caso e por comando. Testes sintáticos não são
execução de firmware. Sanitizadores cobrem apenas os caminhos exercitados.

## Correções desta rodada

- Lifetime compartilhado do display entre instâncias `EglOutput`; antes,
  `eglTerminate` de uma instância podia invalidar as outras. Donos EGL externos
  ainda exigem coordenação explícita, não coberta por essa contagem interna.
- Cleanup RAII das filas de sensores; exceções de inicialização traduzidas no
  limite JNI e exceções do worker impedidas de escapar da thread.
- Evidências e header JNI necessários incluídos no ZIP de fontes independente.
- Regressão para filtros de paths dos workflows, evitando jobs que não disparam
  quando seu próprio arquivo muda.

Ainda faltam boot original, integração dos serviços/compositor, execução da IA e
validação física. Estabilidade de produto exige esses testes, além de sessões
prolongadas com tracking, calor, memória, perda de câmera e pause/resume reais.

### Falha de infraestrutura preservada

O run **36815717226** não chegou à instrumentação: as anotações dos dois jobs
registram **“Timeout waiting for emulator to boot.”** Não há XML de testes; os
relatórios ficam corretamente com `passed: false`. Isso não é aprovação nem prova
de crash do código do renderer. A nova tentativa força KVM, fixa RAM/heap/disco,
desativa Vulkan (a suíte usa GLES), amplia o limite de boot para 900s e captura
logcat desde o boot. Essas medidas são diagnóstico/mitigação, não confirmação da
causa do timeout.


### Confirmed emulator loader failure (run 36817044003)

The captured host diagnostics for both API 29 and 35 report that the emulator's
`qemu-system-x86_64` cannot load `libpulse.so.0`. The failure occurs even for the
`emulator -version` probe, before instrumentation. `-noaudio` does not eliminate
this ELF dependency. The runtime workflow now explicitly installs Ubuntu's
`libpulse0`; this addresses the observed missing dependency, but a new successful
boot and all five instrumented cases are still required before declaring the
runtime gate passed. Earlier RAM/KVM/timeout adjustments did not resolve it.


### Second confirmed boot blocker: userdata disk space

Run `36881685354` used the directly supervised emulator. Both APIs exited before
boot with `Not enough space to create userdata partition`: available 6823.51 MB
(API 29) / 6467.31 MB (API 35), required 7372.80 MB. Setting the AVD data partition
to 2048M did not reduce the system image's actual requirement. The CI workflow now
removes unused preinstalled .NET and CodeQL directories on the disposable runner.
No phone storage or bootloader is touched. Runtime success still requires new
JUnit evidence. The supervisor captures at most 1 MiB of host output and detects
process exit immediately, rather than waiting out a ten/fifteen-minute deadline.

The EGL ownership case also checks ARCore's camera-context guard without creating
an ARCore Session: this exercises real EGL contexts, **not camera or depth**.

Local recheck after adding the emulator supervisor: all project syntax, regression,
JNI-generation and source-bundle checks passed. The native execution recheck also
passed all nine ASan/UBSan cases and both TSan cases. The supervisor has five unit
cases covering configuration deduplication, bounded log storage/draining, early
process exit, exact successful boot-property checking, and boot deadlines. These
synthetic supervisor tests are not emulated Android execution evidence.

### Verified Android adapter runtime recovery

**Run 36883580010 passed on API 29 and API 35**, source commit
`9b6d50e`: exactly five named instrumented cases per API, no failures, no skips,
no missing cases. Evidence is in `analysis/android-runtime/api-{29,35}.json`.
The camera-context ownership guard was included in the real EGL instrumentation.
This closes the missing-library/disk-space/ADB-path CI failures for that run.
It does not execute original Horizon firmware, an ARCore camera/depth session,
Quest hand inference, or a physical Infinix device. No METAPORT release APK is
established by these test APKs.

Before the passing run, `36882551201` progressed through emulator boot but its
shell test launcher failed with exit 127: `adb` was absent from PATH. Both shell
scripts now resolve `${ANDROID_HOME}/platform-tools/adb` explicitly. Two script
fixtures verify SDK paths containing spaces, CheckJNI setup, log cleanup and
preservation of a nonzero Gradle exit. These fixtures simulate commands only;
the passing API 29/35 instrumentation above is the real Android evidence.
