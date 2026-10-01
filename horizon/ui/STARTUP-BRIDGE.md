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
