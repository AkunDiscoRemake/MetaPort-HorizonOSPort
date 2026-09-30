# Resultados observados — candidato Quest 3

**NOT PORTED YET. Versão autorizada/canal estável ainda UNVERIFIED.**

Inspeção executada no GitHub Actions, run `36664095473`, código `536f518`.
Evidência reproduzível: `quest3-candidate-metadata.json` nesta pasta.
A localização em `v2.4/` é a classificação de candidato, não uma certificação.

## O que foi realmente lido

- Metadados textuais do OTA e cabeçalho/manifesto protobuf do `payload.bin`.
- SHA-256 do ZIP corresponde ao catálogo; hash do cabeçalho + manifesto corresponde
  a `METADATA_HASH` do pacote. Assinatura com chave confiável não foi verificada.
- Build declarada: `52168470052900520`, dispositivo `eureka`, Android 14/API 34.
- Payload major 2, minor 0: formato declarado **FULL**, não delta.
- `partial_update` não está ativado; bloco de 4096 bytes.
- 29 partições; soma dos tamanhos declarados: **3.739.418.624 bytes**.
- Apenas operações `REPLACE`, `REPLACE_BZ`, `REPLACE_XZ` observadas.
- Nenhuma dependência de partição anterior declarada nas operações inspecionadas.
- Não foram reconstruídas imagens, verificados seus hashes de saída, examinados
  arquivos de filesystem ou desassemblados executáveis do Horizon OS.

## Consequências para o trabalho

Há evidência de que não precisamos de um OTA de versão fora do escopo como base.
Isso remove uma incerteza de empacotamento, mas não comprova uma VM inicializável.
A reconstrução futura terá de conferir hashes de cada operação e de cada partição,
limites/extents, tamanho de saída e recursos consumidos pela descompressão.
Não tratar `FULL` como garantia de conter estado de provisionamento ou todo o
hardware necessário à execução original.

Partições prioritárias após confirmar escopo:

| Partição | Tamanho declarado (bytes) | Investigação proposta, ainda não realizada |
| --- | ---: | --- |
| system | 954920960 | Framework, linker, serviços e bibliotecas |
| system_ext | 1417265152 | Componentes adicionais; localizar componentes reais por evidência |
| vendor | 531582976 | HALs, bibliotecas de hardware e contratos |
| product | 205205504 | Pacotes, permissões e configuração |
| odm | 295993344 | Customizações do dispositivo |
| boot | 100663296 | Kernel/boot; não fazer flash no Infinix |
| vendor_boot | 100663296 | Ramdisk e dependências de inicialização |

Essas são prioridades de investigação, não conclusões sobre o conteúdo dos arquivos.

## Port em APK: decisão ainda bloqueada

Precisamos identificar ABI/ISA, dependências nativas, IPC, serviços privilegiados e
interfaces gráficas antes de escolher execução userspace, emulação ou combinação.
Não há runtime Horizon inicializado nem backend de hardware implementado. Não existe
base para inventar estruturas de pose/hand tracking, ABI de compositor ou loader XR.

Não usar exploits/root como substituto dos adapters: o alvo permanece APK comum,
bootloader bloqueado e sem alteração do sistema do usuário.

## Limite de escopo pendente

O catálogo associa a build à versão interna `204.0.0.200.1183.996826085`, mas os
metadados lidos não declaram o nome comercial v2.4 nem o canal estável/PTC. A busca
pública pela build exata não resolveu essa correspondência. Não inferir canal pela
presença de `release-keys`. Antes da RE dos componentes, obter evidência de versão e
canal específica desta build (registro de distribuição oficial ou identificação
verificável do sistema de origem). Não reclassificar silenciosamente o escopo.

## Ferramenta implementada

`tools/payload_manifest.py` lê um subconjunto explícito do esquema público AOSP.
Referência de campos: `system/update_engine/update_metadata.proto`, blob
`6d16da40e53720078b2e4f3689dbb296eb325bee`:
https://android.googlesource.com/platform/system/update_engine/+/refs/heads/main/update_metadata.proto

Limites de tamanho, varints, tipos de wire, campos singulares duplicados, nomes de
partição, ranges e hashes de metadados são validados. Campos desconhecidos não são
interpretados; operações desconhecidas são marcadas, não consideradas suportadas.
Isso não é um validador completo de payloads nem um extrator. Não verifica cobertura
integral/overlap dos extents nem assinaturas criptográficas do fabricante.
