# Ponte de inicialização original: evidência atual

O objetivo é executar o caminho original do VrShell, não recriar suas telas.

## O que foi implementado na investigação

- `prepare_shell.py`: confere OTA, partição, APK e `libshell.so`; seleciona sete
  exports originais JNI e verifica que pertencem a regiões executáveis do ELF.
- `TraceShellEntrypoints.java`: registra chamadas diretas e chamadas indiretas
  não resolvidas de JNI_OnLoad, nativeInit, nativeOnDestroy, nativeFrameCommand,
  nativePassthroughRequest, nativeOnSizeChanged e nativeOnLaunchContextReady.
  Seleção de até 24 funções com distribuição entre os pontos de entrada, evitando
  que nativeInit ocupe toda a amostra. Saltos de cauda não são cobertos.
- `loader_audit.py`: percorre as arestas DT_NEEDED já capturadas, sem confundir
  presença no firmware com acesso pelo linker de um APK comum.
- `inspect_platform.py`: extrai/inspeciona as quatro dependências inicialmente
  ausentes do APK; run **36809079029 concluído com sucesso**.
- `prepare_platform_native.py`: seleciona exports versionados exatos de Strata,
  SurfaceTexture, Choreographer e espaços para reconstrução C-like.

## Bloqueios concretos encontrados

A primeira fronteira tinha 39 bibliotecas. Após expandir os quatro ELFs originais,
a auditoria tem **56 nós e 167 arestas capturadas**, incluindo **20 bibliotecas
sem solução demonstrada para APK sem privilégios**. Essa não é a clausura completa.
Os arquivos binários não foram executados.

`libhzos.meta.so` importa serviços/API privados de `libgui`, `libbinder`, `libui`,
`libaudioclient`, `libcamera_metadata`, FMQ e outros. Exporta, entre outros,
`HzuStrata_createLayer`, `HzuStrataLayer_setBuffer` e extensões de SurfaceTexture.
Isso identifica uma fronteira de apresentação a investigar; não prova suas
assinaturas, ownership de buffers, permissões ou ordem de callbacks.

`libhzos_spaces.meta.so` importa `HzuFpHalBroker_getService` de
`libhzos_fphal.meta.so` e exporta `HzuSpaceManager_locateSpace`/`locateSpace2`.
Não basta passar uma matriz ARCore a essas funções: estruturas, relógios,
referenciais e propriedade de handles ainda precisam de recuperação.

Há símbolos importados com versão `LIBBINDER_NDK30`, incluindo
`AStatus_getDescription`, no relatório. O piso API 29 dos nossos adaptadores
não certifica o runtime original nem sua compatibilidade de símbolos.

## Execuções disparadas

- **36808853419:** inicialização JNI original e fronteira de chamadas nativas.
- **36809468975:** corpos originais de 12 funções de superfícies/cadência e nove
  funções de espaços. Em andamento no momento deste registro.

Resultados ficam em `analysis/builds/52168470052900520/shell-*.json` e preservam
hashes, escopo, truncamentos e status. Workflow verde não significa APK funcional.
Não chamar ponteiros privados com assinaturas inferidas pelo decompilador.

## Resultados efetivamente concluídos

Run **36809468975** passou e reconstruiu os 21 exports selecionados. Observações
confirmadas nos corpos e referências capturados, ainda **sem ABI executável**:

- `HzuSpaceManager_create` chama `HzuFpHalBroker_getService` com o nome
  `horizonos.spaces.spacemanager.ISpaceManager` e instância `default`.
- `locateSpace`/`locateSpace2` chamam o serviço por tabela de funções e convertem a
  resposta com `toHzuSpaceData`/`toHzuBaseSpaceData` e variantes. O teste de palavra
  `0x55` é observado; seu significado formal ainda não foi estabelecido.
- `HzuStrata_createLayer` usa o serviço através de objeto Binder e mantém referências
  fortes. `setBuffer` passa por `convertToHardwareBuffer`, não entrega uma textura
  GLES arbitrária diretamente ao compositor.
- `HzuChoreographer_create` exige SurfaceControl associado à janela e Looper na
  thread; ambos têm caminhos de erro explícitos. A troca por um callback genérico
  de frame não foi demonstrada equivalente.
- `ASurfaceTexture_create` constrói BufferQueue/SurfaceTexture privados e consulta
  display/contexto EGL. Não é prova de intercambialidade com a API pública homônima.

A análise seguinte acrescenta seis alvos internos observados diretamente nesses
relatórios (construtor Strata, conversão de hardware buffer e quatro conversores
espaciais), mantendo os hashes exatos. Não gera stubs de sucesso para o serviço.

## Inicialização JNI: resultado e contradição que bloqueia implementação cega

Run **36808853419 concluído com sucesso de análise**. Os sete exports selecionados
foram reconstruídos, com helpers diretos amostrados. `nativeInit` exige que não
exista uma instância nativa anterior; o caminho de duplicação aborta. Isso é
controle de lifecycle, não detector de root/VR a remover indiscriminadamente.

`nativePassthroughRequest` enfileira uma mensagem identificada por `0x14`, com
payload alocado de `0x68` bytes e marca `5`. Isso não executa por si só captura ou
renderização. O consumidor e o significado do argumento inteiro continuam pendentes.

**Há uma divergência de tipos:** o Java reconstruído declara `long nativeInit(...)`,
enquanto o Ghidra emitiu `void` e avisos de no-return em wrappers de delete.
`analysis/builds/52168470052900520/shell-init-abi-discrepancy.json` registra essa
contradição. Não transformar a assinatura C-like em header utilizável sem conferir
o descritor DEX, retorno ARM64 e comportamento dos wrappers. A causa não foi provada.

## Conversores internos e primeiro componente C++ desta ponte

Run **36809949550** terminou com sucesso. A análise acrescentou os quatro
conversores espaciais e os helpers de Strata/buffer. O construtor Strata procura
explicitamente o serviço Binder `Strata`, reforçando que não é uma janela EGL local.

A cópia dos quatro payloads espaciais foi adaptada em `space_data.cpp` e ligada ao
build Android, com testes locais ASan/UBSan passando. Veja `port/android/SPACE-DATA.md`
para offsets, limites e diferenças da API própria em relação ao código original.
O teste Android/ARM64-QEMU **36810507577** foi iniciado; teste físico permanece ausente.

Validação final desta etapa: **36810507577 passou**, incluindo o novo teste de
cópia espacial em ARM64/QEMU e o build/lint Android. As análises nativas
**36808853419**, **36809468975** e **36809949550** também terminaram com sucesso
nos seus escopos estáticos. Não há um serviço Strata/SpaceManager portado executando.

## Original DEX / ARM64 return verification

Actions **36812160938 succeeded**. `shell-jni-abi-proof.json` verifies the pinned
original APK, DEX checksums and native declarations, and original executable ELF
bytes without loading firmware. `nativeInit` has the original descriptor
`(Lcom/oculus/vrshell/ShellApplication;JLjava/lang/String;Ljava/lang/String;ZZ)J`.
Its normal ARM64 epilogue loads a 64-bit value from ELF global `0x275b008` into
`X0` and preserves it through `RET`. The service setter stores to that same slot.
The return-type discrepancy is therefore resolved **for the normal return path**:
the inferred Ghidra `void` declaration must not become the JNI adapter signature.
This does not establish constructor success, ownership, exception behavior or a
complete callable private ABI.

Raw bytes also contain branches after both cleanup calls that were absent from
the earlier Ghidra function-body listing: `0xd78d5c -> 0xd78d14` and
`0xd78d68 -> 0xd78d1c`. The original libc++ `__wrap__ZdlPv` export has a nonzero
address (`0x47444`) but **zero ELF symbol size**. Its first instruction branches
to `0x83e10`; the captured 16-byte window is not a proven function extent, and
subsequent instructions may belong to other entries. The target implementation
and the cause of Ghidra's no-return inference remain unverified. No allocator
replacement is justified by this evidence alone.

The first proof run, 36811921551, rejected the zero-size symbol. The verifier now
reports bounded wrapper evidence separately rather than treating missing size as
proof of an invalid function. Local suites: **36 UI tests passed; 92 hand-analysis
tests ran successfully with one skip** (dependencies installed).

A separate `shell-threads.yml` analysis now follows five internal candidates
referenced by the pinned startup report: the thread target and trampoline,
service destruction, preferences symbol lookup, and thread lifecycle helper.
Their names/purposes remain analysis hypotheses, not original API declarations.
The selector verifies source-library hash, reference provenance and executable
address bounds; neither workflow executes firmware or produces a working APK.

## Thread → original ShellApp → frame loop

Run **36812219346 succeeded**, recovering five seeds and nine direct callees.
The report remains C-like reconstruction, not a compiled or executed port.

- ELF `0xd8a0b4` prepares a `0x890`-byte stack region, invokes `0xd5d3d8`, then
  `0xd8e01c` and a thread-rundown helper. This does not establish a public C++
  object layout for reuse by our code.
- `0xd5d3d8` includes `ShellApp::ShellApp`, identity readiness, JavaVM thread
  attachment, Clay initialization/startup, a non-null VR-platform invariant,
  controller/environment/input setup, and the original frame loop. The frame
  iteration invokes `0xd622fc`. Its large decompilation contains indirect calls
  and allocator no-return warnings; do not compile it as recovered source.
- Service destruction at `0xd8a254` signals stop and calls rundown with 200 ms
  waits and a retry argument of 20. It also contains `_Exit(0)`, not just ordinary
  object destruction. This is an explicit process-lifecycle integration issue,
  not evidence of root detection and not permission to remove checks blindly.
- The preferences accessor uses `call_once` with callback `0xd8a760` (callback
  bodies were not followed by the earlier direct-CALL-only frontier).

Run **36812746651 succeeded** in tracing original `__wrap__ZdlPv` from `0x47444`
through PLT `0x83e10` to GOT `0x8f120`, whose relocation names **`free@LIBC`**.
This resolves the static tail destination, not runtime symbol interposition or
all exception paths. It contradicts treating the wrapper's zero symbol size as
absence of an implementation; Ghidra's no-return inference still needs correction
before relying on reconstructed cleanup control flow.

`generate_jni_contract.py` generates type-only C++ function pointers from all
native declarations recovered from the original target DEX class. The Android
build now compiles startup signature assertions with actual NDK JNI types.
There are **no fake JNI implementations or success stubs**. Notably, the exported
`nativePassthroughRequest` selected in the original ELF study has **no matching
native declaration in this DEX class**; export presence alone does not prove a
reachable Java API. The generated contract deliberately does not invent one.

Next bounded analysis: **36813678532**, eight identity/Clay/platform/frame
candidates, still pending at this update. Android contract build **36813604224 succeeded**: NDK compilation, native tests,
Java tests and lint passed. The output remains an AAR, not an APK. Local validation: **45 UI tests passed; 92 hand-analysis tests ran,
one skipped**. A working METAPORT APK and device rendering are still unvalidated.

## FrameFunction: recuperação parcial e fronteira real de runtime

Run **36813678532 falhou na validação**, preservando 23 reconstruções C-like de
24 funções. O construtor em ELF `0xdc8480` excedeu 30 segundos; seu prefixo de
instruções também está truncado. Não foi convertido em sucesso silencioso.

Evidências recuperadas, ainda sem execução/ABI privada validada:

- `0xd61360` aguarda identidade; o corpo contém a mensagem “No user in 60s.
  Bailing.” e `_Exit(0)`. Isso não autoriza inventar uma identidade ou burlar auth.
- `0xd622fc` contém `ShellApp::FrameFunction`, exige estado VrApi, chama a
  preparação de frame Clay e sinaliza parada quando perde `xrInstance` ou essa
  preparação falha. A submissão de frame usa chamada virtual; não basta trocar
  a saída por `eglSwapBuffers`.
- `0xd8a760` resolve `createPreferencesManager` por `dlsym`, após accessor com
  `call_once`; o callback de carga a seguir é ELF `0xd8a5e8`.
- As funções `0xd8bc20` / `0xd8befc`, inicialmente rotuladas como candidatas a
  init/start, constroem opções/mapas de recursos. Os status de init/start são
  consultados por chamadas a **`0xbbd334` / `0x1b5ed50`** na reconstrução.
- `ShellApp` aloca `0x740` bytes e chama **`0x111fb2c`**; o objeto é depois
  atribuído ao slot identificado como `vrPlatform_` pelo invariant textual.
  Isso é uma pista para constructor/vtable, não uma definição de struct/ABI.
- O caminho Clay padrão aloca com alinhamento `0x40` e chama **`0xdaebf0`**;
  há também um caminho de factory indireta. Não substituímos ambos por stubs.

`TraceShellBatch.java` amplia a recuperação para até 96 funções por importação,
com seleção em dois níveis, gravação incremental, limites explícitos e progresso
no log. A função que excedeu o limite recebe 180s, sem multiplicar esse orçamento
por todas as demais. Listing de 256 instruções e C-like de até 200 mil caracteres
por função têm truncamentos/falhas explícitos. **Não é disassembly completo de
Horizon**. A seleção ampliada segue também identidade, interação de janela,
callback de carga e preparação de frame; um job paralelo segue os quatro alvos
concretos de plataforma/Clay acima.

Checagens de runtime dos nossos adaptadores, separadas dessas inferências:
`docs/VALIDATION.md`. Executar nossa JNI não significa executar a JNI original.
