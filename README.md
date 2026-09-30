# MetaPort — Horizon OS → Android + VRBox

**NOT PORTED YET. Ainda não há APK do Horizon OS funcionando.**

Objetivo: portar componentes originais, preservando arquitetura e comportamento,
sem UI falsa, launcher substituto ou runtime simulado apresentado como funcional.

## Escopo e alvo

- **Todas as versões**, conforme nova autorização informada pelo solicitante.
  [Política vigente](analysis/SCOPE.md). Não há verificação independente dessa
  autorização ou comprovação de direitos de redistribuição.
- **Infinix GT30 Pro X6873 / XOS 16.2**, conforme relato do usuário.
- **APK comum**, bootloader bloqueado, sem root, desbloqueio ou flash.
- Nenhum teste físico no telefone; API/ABI/capacidades efetivas ainda não medidas.

## Trabalho realizado

O pacote Quest 3 da build `52168470052900520`, fixado por SHA-256, foi baixado e
analisado em GitHub Actions. O pipeline já:

1. Inventariou o OTA e leu seu manifesto FULL com 29 partições.
2. Reconstruiu todas as **29 partições do OTA**, conferindo os hashes de cada
   operação e de cada imagem final (3,74 GB).
3. Inventariou filesystems ext4 sem mount e inspecionou três APEX Meta.
4. Localizou System UI, VrShell, VrDriver, tracking, compositor e o caminho OpenXR.
5. Leu manifestos de cinco APKs e analisou bibliotecas nativas selecionadas.
6. Produziu disassembly ARM64 amostral e `.text` completa de bibliotecas menores
   selecionadas, dependências, símbolos e evidências do protocolo Binder original.
7. Compilou o kernel público Meta com adaptação virtual e **executou o primeiro
   estágio do init original em QEMU**, no caminho de boot normal. Parou esperando
   partições guest ainda não anexadas; não houve boot completo.

**[Estado do firmware completo e bloqueios de boot](analysis/builds/52168470052900520/FIRMWARE-STATUS.md)**

**[Resultado do primeiro estágio original em guest](analysis/builds/52168470052900520/GUEST-BOOT.md)**

[Mapa anterior de userspace](analysis/builds/52168470052900520/PORTING-MAP.md).

Isso reúne análise de componentes originais e um primeiro experimento de boot,
não um sistema portado funcional. DEX ainda não foi decompilado; o disassembly é amostral, não completo.
Não houve boot completo do Android/Horizon, integração de hardware original
ou otimização medida. O primeiro estágio executado não abriu Home/System UI.
A principal barreira observada é a dependência em serviços/UIDs/capacidades de
sistema, IPC e interfaces vendor que um APK comum não recebe.

## Ferramentas

Python 3.10+ em Linux. Inventário, inspeção e reconstrução usam a biblioteca padrão.
Análise de filesystem/ELF/APK requer ferramentas **do host**:
`debugfs`/`mke2fs` (e2fsprogs), `readelf`, `aarch64-linux-gnu-objdump` e `aapt`.
Nunca executar programas extraídos diretamente no host. O teste em `guest/`
usa emulação isolada em runner descartável, não execução nativa nem flash.

```sh
python3 -m unittest discover -s tests -v

# Quando o ZIP fixado já estiver disponível localmente:
mkdir -p local-analysis
python3 -m tools.inspect_ota --manifest \
  artifacts/incoming/q3_52168470052900520.zip \
  --output local-analysis/ota-report.json
python3 -m tools.reconstruct_ota --all-partitions \
  artifacts/incoming/q3_52168470052900520.zip \
  --directory local-analysis/images \
  --report local-analysis/reconstruction.json
python3 -m tools.scan_partitions \
  --images local-analysis/images \
  --reconstruction-report local-analysis/reconstruction.json \
  --output local-analysis/static-analysis.json
```

A reconstrução exige diretório de saída vazio e espaço livre para ZIP + imagens.
Não aceita operações delta, desconhecidas, sobreposição/gaps ou hashes divergentes.
Arquivos malformados e formatos não suportados não devem ser tratados como sucesso.
A análise usa limites de tamanho e subprocessos com timeout, mas não constitui uma
sandbox geral: executá-la em ambiente isolado e descartável, como o runner.

`tools/inventory.py` produz SHA-256 e proveniência para outras coleções locais.
`tools/device_probe.py` faz um preflight ADB opcional e somente leitura do telefone;
não é um APK, não instala nada e não comprova compatibilidade XR.

## GitHub Actions e armazenamento

`.github/workflows/fetch-firmware.yml` baixa apenas o pacote fixado, verifica hashes,
reconstrói imagens, analisa arquivos e publica relatórios nesta branch. Não instala
firmware no celular. A execução pode falhar por rede, cota ou limite do parser.
Relatórios são publicados mesmo quando etapas posteriores falham; sempre conferir
os estados individuais e a execução de origem, não apenas a existência do JSON.

Firmware, imagens e arquivos temporários **não entram no Git**. `artifacts/` e
`local-analysis/` são ignorados. O workflow atual não publica novos artifacts de
firmware: só relatórios (retenção de sete dias). Os artifacts de firmware das
primeiras execuções tinham retenção de um dia. O `.gitignore` não é armazenamento
remoto e não transfere arquivos do telefone.

Resultados históricos em `analysis/v2.4/` precedem a ampliação de escopo.
O número comercial/canal da build permanece incerto; hashes não autenticam assinaturas.
Nenhuma outra versão é baixada automaticamente e não há seleção de “latest”.

## Backends Android implementados

Há agora um módulo [Android/NDK de adapters](port/android/README.md), sem UI ou
Activity, com aquisição real de sensores, backend ARCore e saída EGL/GLES.
O workflow próprio compila o AAR arm64, roda testes C++/JVM e Android lint.
**Não é APK nem bridge Horizon concluída.** Não houve teste físico; o transporte
MemoryBroker/Binder original ainda precisa ser ligado aos backends.
