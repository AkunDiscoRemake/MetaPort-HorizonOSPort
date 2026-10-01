# MetaPort HandTracking

Subsistema separado do MetaPort, com uma única implementação compartilhada.
**Estado: recuperação/port parcial. Não é APK, instalador ou IA de mãos pronta.**

## Download publicado

[ZIP com originais recuperados — 183,7 MB](https://github.com/AkunDiscoRemake/MetaPort-HorizonOSPort/releases/download/handtracking-recovered-36799154034-1/MetaPort-HandTracking-recovered.zip)

[Fontes — 3,1 MB](https://github.com/AkunDiscoRemake/MetaPort-HorizonOSPort/releases/download/handtracking-recovered-36799154034-1/MetaPort-HandTracking-sources.zip) · [Release e SHA-256](https://github.com/AkunDiscoRemake/MetaPort-HorizonOSPort/releases/tag/handtracking-recovered-36799154034-1)

Build do pacote **36799154034** e build Android **36799130880** concluídos com sucesso.
Inclui 41 arquivos originais verificados, mais dez modelos descomprimidos. É um
pacote de recuperação/port parcial, não um APK nem inferência funcional.

## Não contém apenas otimizações

- `ai/`: ferramentas de inspeção da IA original, ETZ0/PTE/FlatBuffers, atributos,
  constantes, modelos, geometria/animação, Ghidra, contratos e testes.
- `native/`: componentes C++ portados/adaptados: redução inteira, packing saturado,
  regra de atualização de material, cálculo de arenas, paleta e planejamento FMQ.
- `distribution/originals.json`: catálogo pinado dos **21 arquivos de modelos**
  identificados no firmware Quest 3 (detecção, DPE, microgestos, teclado e touchpad),
  quatro assets visuais e componentes originais de runtime/dependências.
- O ZIP **recovered** acrescenta os arquivos originais desse catálogo, incluindo
  pesos/programas `.ptl`/`.ptez`, engine e backend DSP inspecionado. Os dez `.ptez`
  também são descomprimidos para `.pte`, com os hashes conferidos. Nenhum modelo
  é executado na criação do pacote; pickle nunca é carregado/executado.
- O ZIP **sources** não contém esses binários. `PACKAGE-MANIFEST.json` distingue
  os modos e lista cada arquivo com tamanho e SHA-256.

**Isso não é “toda a IA Quest 3 portada”**: ter os pesos e binários originais não
faz o Hexagon do Quest funcionar no MediaTek. O catálogo é completo para os 25
recursos handtracking inventariados, não para todas as dependências, otimizações
ou versões do Horizon OS. Consulte `component.json` e os relatórios em `analysis/`.

## Reutilização pelo MetaPort

`port/android/adapters/src/main/cpp/CMakeLists.txt` adiciona este diretório como
subprojeto e liga `metaport_handtracking_objects`. Não mantém cópias dos helpers.
A integração é real no **build nativo**; não implica que a inferência original já
esteja conectada à câmera ou à UI. Os binários proprietários do ZIP não são
injetados automaticamente no APK nem renomeados como bibliotecas Android.

Outro aplicativo C++ pode usar `add_subdirectory(handtracking)` e
`target_link_libraries(seu_target PRIVATE metaport_handtracking)`.

## Build independente e testes

A partir da raiz do repositório ou do ZIP descompactado:

```sh
cmake -S handtracking -B build-hand -DMETAPORT_HANDTRACKING_BUILD_TESTS=ON -DCMAKE_BUILD_TYPE=Release
cmake --build build-hand
ctest --test-dir build-hand --output-on-failure
python3 -m pip install -r handtracking/ai/requirements.txt
python3 -m unittest discover -s handtracking/ai/tests -v
```

C++17 e CMake >=3.22.1; testes nativos não exigem Android. No ARM64, os helpers
SIMD usam NEON. Testes aritméticos não são execução da IA ou validação do telefone.
As ferramentas offline usam também os utilitários compartilhados de `tools/`;
extração de imagens exige Linux, `debugfs` e `readelf`.
Os comandos Python antigos `horizon.tracking.*` migraram para `handtracking.ai.*`.

## ZIP e verificação

```sh
python3 -m handtracking.distribution.package --output artifacts/MetaPort-HandTracking-sources.zip
python3 -m handtracking.distribution.package --verify artifacts/MetaPort-HandTracking-sources.zip
```

O workflow `Package MetaPort HandTracking` reconstrói ODM/vendor da OTA pinada,
confere partições e cada recurso, gera o ZIP recovered, verifica seu conteúdo e
publica uma **prerelease**, explicitamente incompleta. Não inclui a OTA nem imagens
de partições no ZIP. Baixar e extrair o ZIP não altera bootloader, root ou sistema.

## Licenças

Código próprio: GPL-3.0-only, ver `LICENSE` e `NOTICE.md` na raiz do pacote.
Modelos, firmware, assets Meta e outros componentes mantêm os direitos/licenças
originais: **não são relicenciados como GPL**. O solicitante relatou autorização;
isso não foi verificado independentemente. O pacote não concede direitos sobre
componentes de terceiros. Veja também `THIRD-PARTY-NOTICE.md`.

## Desassemblagem integral das seções executáveis do engine

`hand-engine-disassembly.yml` agora extrai o `libtrackingengines.so` original
pinado (SHA-256 `10eac37188c97389dabfe7599a354d146d1e6223d849546d230796af93418ffe`,
41.154.352 bytes) e gera a listagem das seções executáveis, incluindo regiões
zeradas, em gzip. O pipeline verifica a imagem ODM e o ELF antes de analisar.
O JSON de proveniência é publicado no Git; a listagem fica em artefato do Actions
por sete dias. Isso cobre **uma biblioteca ARM64**, não todos os modelos/DSPs,
nem prova que todas as otimizações foram identificadas ou que a IA executa.

A primeira execução, **36884576681**, concluiu com sucesso: **8.277.719 linhas de
instruções**, 400.473.978 bytes de texto e **71.540.451 bytes de gzip**. Metadados:
`analysis/builds/52168470052900520/hand-engine-full-disassembly.json`. Artefato:
`original-tracking-engine-executable-sections-not-inference`. Nenhuma inferência
foi executada por essa análise.
