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

## Atualização: transporte AIDL parcialmente recuperado

O disassembly completo da `.text` de `memorybrokerservice-aidl-V2-ndk.so` e o VINTF
permitiram registrar serviço, quatro códigos de transação e ordem de serialização
parcial de `MemoryAllocation` em [abi/52168470052900520.json](abi/52168470052900520.json).
Cada call site está ligado ao SHA-256 do ELF e verificado por testes contra a
captura estática. **Isso não é teste de conformidade em runtime.**

O serviço é `oculus.internal.tracking.IMemoryBrokerService/default`, VINTF AIDL v2.
Restam os valores numéricos dos enums, semântica dos campos/poses, regras de
sincronização, lifecycle e execução no guest. Não foi implementado servidor falso.

## Nova inspeção de engine, modelos, UI e clients

O engine de 41 MB e os clients foram analisados com Ghidra; 24 funções de cada
biblioteca foram reconstruídas como C-like não validado. O registry anuncia ABI 36
e a factory HandTracker seleciona versões 11–14. Não foram inferidos headers de
vtable nem implementado um provider falso a partir desses números.

Há também decompilação DEX de VrShell/MetaSystemUI, evidências dos call sites de
entrada e um backend Android/C++ de Joy-Cons ainda não ligado ao runtime privado.
Ver [resultados medidos e bloqueios](../../analysis/builds/52168470052900520/HANDS-UI-INPUT.md).

## Containers e planos dos modelos originais

O decoder offline recuperou dez programas ET12 a partir de etz0/deflate. Há agora
metadados limitados de tensores, constantes e referências de instruções, ligados
a hashes em `ptez-report.json`. Os DPE31/32 possuem dois DelegateCall para
HexagonRpcBackend no plano forward analisado. Não há inferência nem tradução
desses delegates para o telefone. Veja [a continuação medida](../../analysis/builds/52168470052900520/COMPRESSED-HAND-MODELS.md).

## Atributos DPE e verificação independente

O getter constante `get_attributes_msgpack` foi inspecionado sem execução:
DPE31/32 declaram `[96,96]`, `use_uint8_input=false` e formato privado `v2`.
Não confundir esse frontend com o tensor Byte quantizado do grafo compilado,
nem conectar bytes da Camera2 sem recuperar a conversão e calibração originais.

Um probe C++ com schema público verificou os dez programas e recuperou em Int64
os 13 escalares recusados pelo limite conservador de extensão de objeto. O writer
público FlatBuffers reproduz a vtable compartilhada que causa a advertência;
isso não identifica o exporter privado ou valida inferência. Veja [evidências,
constantes e testes](../../analysis/builds/52168470052900520/ATTRIBUTES-REFERENCE-VALIDATION.md).
**O bridge de câmera/mãos continua NOT PORTED YET.**
