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
