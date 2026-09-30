# Contrato de tracking observado — não substituído por ABI fictícia

**Bridge Horizon ↔ backends Android: NOT PORTED YET.**

Base: build `52168470052900520`, relatório estático em
`analysis/builds/52168470052900520/static-analysis.json`.
Os adapters compilados em `port/android/` são produtores de dados reais do Android;
não exportam os símbolos abaixo nem afirmam equivalência com o transporte original.

## Símbolos originais observados

`odm:/lib64/libhzos_trackinghost.meta.so`:

- `MemoryBroker_HostConnection_create@@LIBHZOS_TRACKINGHOST`
- `MemoryBroker_HostConnection_destroy@@LIBHZOS_TRACKINGHOST`
- `MemoryBroker_HostConnection_registerSubRegion@@LIBHZOS_TRACKINGHOST`

`system_ext:/lib64/libhzos_trackingclient.meta.so` e variante internal no ODM:

- `MemoryBroker_ClientConnection_create`
- `MemoryBroker_ClientConnection_destroy`
- `MemoryBroker_ClientConnection_acquireSubRegion`
- `MemoryBroker_ClientConnection_getRegionPtr`
- `MemoryBroker_ClientConnection_releaseRegion`

Importam `libmemorybrokerclient.so`, Binder NDK e tipos de
`aidl::oculus::internal::tracking` nas assinaturas C++ mangled.
Não há evidência de que esses wrappers aceitem diretamente um quaternion/xyz.

## Observações da implementação ARM64 do host

Os endereços abaixo são virtuais do ELF analisado, **não offsets válidos para
qualquer versão**. Símbolo `registerSubRegion` em `0x10b0`:

- `0x10cc` e `0x10d0`: validação de argumentos x0 e x1 não nulos.
- `0x10d4`: leitura de 32 bits em `[x1+0]`; valor é validado e remapeado por tabela.
- `0x10f0`: leitura de 32 bits em `[x1+4]`, com outro remapeamento.
- `0x114c`: leitura de 32 bits em `[x1+8]` para w3.
- `0x1144`: leitura de dois campos de 64 bits em `[x1+16]` e `[x1+24]`.
- `0x1164`: chamada de `memorybroker::HostConnection::registerRegion` com tipos
  `SharedMemoryType`, `SharedMemorySpecifierType`, tamanho unsigned long e
  `std::function<void(void*)>`.
- `0x1290–0x1298`: thunk carrega um ponteiro de função e seu contexto, lê um ponteiro
  de dados e faz branch indireto.

**Inferência ainda não validada:** o descritor de registro parece conter enums,
tamanho e callback/contexto. Isso NÃO fornece o layout das poses na região, valores
semânticos dos enums, sincronização, serialização Binder ou contrato de lifecycle.
Não gerar um header ABI definitivo a partir só dessas leituras.

## Itens que faltam para conectar o adapter de verdade

1. Recuperar tabelas de remapeamento, nomes/IDs de regiões e serviço Binder.
2. Inspecionar o `registerRegion` real e os leitores de cada região no runtime.
3. Determinar layout, alinhamento, versionamento, ownership e mecanismo de
   sincronização (atomics/seqlock/fences/etc.) por região; não presumir qual é usado.
4. Identificar unidades, timestamps, origem, coordenadas e flags de validade das poses.
5. Medir extrínseca câmera→cabeça/olhos no telefone/VRBox; pose de câmera não é pose
   de cabeça nem de olho. Definir política de re-localização/origem compatível.
6. Implementar a bridge sem publicar sucesso quando IPC ou hardware não existem.
7. Validar contra os componentes originais em execução e contra o telefone físico.

A interface Java/C++ interna do MetaPort não deve ser instalada como substituta de
`libhzos_trackinghost.meta.so`. Nenhum símbolo original foi exportado como stub.
