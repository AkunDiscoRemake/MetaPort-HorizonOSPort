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
7. Compilou o kernel público Meta com adaptação virtual e executou o init original.
8. Construiu o armazenamento guest, **montou as sete partições originais e
   executou o segundo estágio do init**. Ensaios anteriores alcançaram post-fs-data,
   sem boot completo. O ensaio atual com userdata descartável espera o Keystore
   durante o provisionamento criptográfico; não abre o Horizon.
   [Resultado do ensaio com userdata](analysis/builds/52168470052900520/GUEST-USERDATA.md).

**[Estado do firmware completo e bloqueios de boot](analysis/builds/52168470052900520/FIRMWARE-STATUS.md)**

**[Resultado atual: partições e segundo estágio originais](analysis/builds/52168470052900520/GUEST-STORAGE.md)**

**[Resultado inicial do primeiro estágio original em guest](analysis/builds/52168470052900520/GUEST-BOOT.md)**

[Mapa anterior de userspace](analysis/builds/52168470052900520/PORTING-MAP.md).

Isso reúne análise de componentes originais e um primeiro experimento de boot,
não um sistema portado funcional. Há decompilação limitada de DEX e funções nativas,
com erros/tipos inferidos ainda não validados; não é recuperação completa do código.
Não houve boot completo do Android/Horizon, integração de hardware original
ou otimização de desempenho medida no telefone. O segundo estágio executado não demonstra Home/System UI funcionando.
A principal barreira observada é a dependência em serviços/UIDs/capacidades de
sistema, IPC e interfaces vendor que um APK comum não recebe.

## Foco atual: hand tracking original

- Preparação sem perda das malhas esquerda/direita, preservando UVs e até sete
  influências por vértice; comparação integral dos buffers com os assets originais.
- Paleta compacta de 17 nós, sem eliminar a hierarquia original de 79 nós.
- Transferência nativa de registros da paleta sem alocação por frame, compilada no
  AAR Android ARM64 e testada com ASan/UBSan; ainda sem bridge de poses/renderer.
- Caminho visual original localizado em `libshell.so`, incluindo aquisição de
  mesh por OpenXR e parâmetros do material das mãos. Não se presume que a mesh
  do tracking seja a mesma fornecida ao VrShell.

[Medidas, implementação e bloqueios de animação/renderização](analysis/builds/52168470052900520/HAND-VISUALS.md).
**Não há hand tracking completo funcionando no telefone.**

## Diagnóstico atual do BootControl

[Negação SELinux e resultado dos testes de rotulagem](analysis/builds/52168470052900520/BOOTCONTROL-LABELS.md).
O HAL recebe `vd_device` ao acessar misc; os testes confirmaram a negação.
A tabela corretiva foi gerada, mas sua aplicação foi recusada. O experimento
ficou desativado por padrão; não é uma correção concluída.

## APK, Cardboard e Store Meta

[Estado da integração e dependências verificadas](analysis/builds/52168470052900520/APK-AND-META-SERVICES.md).
Os manifests originais da Store e autenticação foram inspecionados; isso não é
login nem acesso à loja. O teste com DT/disco adaptados ainda espera o BootControl HAL.
Não há APK funcional, conexão a conta Meta ou desempenho VR comprovado.

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
A sondagem não coleta recursos VR, estado do bootloader ou Verified Boot, nem
faz detecção de root. Ausência de recursos declarados não bloqueia a sondagem.
O código Android atual não exige um recurso de sistema VR nem contém detector de
root. Isso não afirma que componentes proprietários ainda não portados tenham sido
modificados; validações de permissões e hashes de firmware continuam necessárias.

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

## Licença

O código próprio do MetaPort está sob **GNU GPLv3 (GPL-3.0-only)** — texto completo
em [LICENSE](LICENSE). Componentes proprietários, fontes externas e evidências
extraídas mantêm os direitos e licenças aplicáveis; consulte [NOTICE.md](NOTICE.md).
Esta licença não concede direitos sobre o firmware da Meta nem torna o port pronto.

## Subsistema de hand tracking separado

[MetaPort HandTracking](handtracking/README.md) contém as ferramentas da IA original,
componentes nativos compartilhados e empacotamento verificável. O MetaPort o utiliza
como dependência CMake, sem duplicar implementações. **Inferência original completa
ainda NÃO PORTADA**; ZIP recovered não equivale a APK funcional.

[Baixar ZIP do hand tracking com originais recuperados](https://github.com/AkunDiscoRemake/MetaPort-HorizonOSPort/releases/tag/handtracking-recovered-36799154034-1)

## Continuação: UI/UX original e passthrough

- [Decompilação e fronteiras do port da UI original](horizon/ui/README.md)
- [Evidências, falhas e validações desta etapa](horizon/ui/PORT-STATUS.md)
- [Fundo de câmera físico compartilhado com ARCore](port/android/PASSTHROUGH.md)

O componente de câmera passou no build Android, mas ainda não está ligado ao
compositor Horizon; não equivale ao passthrough estéreo do Quest nem a APK pronto.

## Público, requisitos e compatibilidade

[Requisitos preliminares e protocolo de validação](docs/COMPATIBILITY.md).
Não há compatibilidade universal, lista de aparelhos certificados ou mínimo
funcional medido. Os orçamentos de hardware são alvos para a futura alfa, não
recomendação de compra nem garantia de executar Horizon. O objetivo continua
sendo portar o software original, e não substituir a experiência por um demo.

[Método de port: decompilação, disassembly, QEMU e critérios de execução original](docs/PORTING-METHOD.md).
