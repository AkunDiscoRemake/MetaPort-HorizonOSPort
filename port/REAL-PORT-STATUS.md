# Marco: primeiro APK original funcional (ainda não atingido)

Não publicar demo, launcher/WebView ou biblioteca AAR como “Quest completo”.
AAR é componente de build; não é aplicativo instalável.

| Área | Implementado/recuperado | Bloqueio para o marco |
|---|---|---|
| UI/configurações | Decompilação original de cinco APKs; manifesto, JNI, Binder e recursos | Recompilar/ligar código original, resolver classes privadas e permissões; erros JADX e arquivos omitidos explicitamente |
| Mãos | 21 containers originais, dez PTE descomprimidos; módulo nativo compartilhado | Inferência DPE usa HexagonRpcBackend; falta backend compatível no MediaTek, formatos/calibração e comparação numérica |
| Passthrough | Pass OES da câmera ARCore, sem readback de imagem para Java | Ligar ao compositor original; não há captura estéreo/reprojeção/oclusão Quest |
| Depth Android | Aquisição real opcional AUTOMATIC/RAW, confiança raw e timestamps, leitura com stride | Suporte e validação física no Infinix; não é algoritmo Meta |
| Depth Quest | Dois modelos mldepth e tuning localizados; inspeção original iniciada | Consumidor, entradas, calibração, kernels e execução original não recuperados integralmente |
| Store/cloud | Extração/decompilação dos clientes originais iniciada | Backend Meta, fluxo autorizado de autenticação, entitlement e permissões reais; não reproduzidos por APK |

Build Android **36805393417: sucesso** após implementação de depth, incluindo testes
Java e lint. Isso não mede câmera/depth/shader no aparelho.

Execuções iniciadas nesta etapa:
- UI/configurações: **36805504164**.
- Store/identidade/DeviceAuth/OCMS/social: **36805504240**.
- Modelos depth originais: **36805607831**.

## O que bloqueará a alegação de APK funcional

Exigir boot do cliente original, apresentação original, entrada real e teste de
ciclo pause/resume no aparelho. Habilitar mãos somente após resultados reais da
inferência original; depth somente com dados de origem identificada. Cada função
de configuração deve ter seu efeito real comprovado, não apenas botão visível.
Store exige catálogo/autenticação/entitlement reais por integração autorizada;
não simular compras nem contornar assinaturas/atestação ou permissões do Android.

O sensor/câmera ausente não é criado pelo VRBox. APIs signature/privileged não
ficam disponíveis a APK comum só por recompilar. Alguns recursos podem exigir
cooperação da Meta/fabricante ou ser inviáveis sob o requisito de APK sem
privilégios e bootloader bloqueado. “Ainda não portado” não é promessa de que
todo recurso do Quest poderá ser reproduzido nesse hardware.

## Atualização: revisão dos jobs e preparação para público

Os runs UI **36805504164** e cloud **36805504240** terminaram com sucesso de análise,
com erros/omissões de decompilação descritos em `docs/PORTING-METHOD.md`. Isso não
altera os bloqueios de execução da tabela acima. O run depth **36805607831** também
terminou; o formato dos modelos permanece opaco (TH1).

Requisitos preliminares: `docs/COMPATIBILITY.md`; política verificável em
`devices/compatibility-policy.json`. Nenhum modelo de telefone validado fisicamente,
sem promessa de compatibilidade universal ou APK completo.

## Inicialização original: progresso sem APK funcional

A análise 36812219346 recuperou a cadeia da thread até `ShellApp` e seu laço de
frames. Há dependências explícitas de identidade, Clay e plataforma VR antes do
loop; o encerramento do serviço inclui `_Exit(0)`. A ligação JNI agora tem tipos
C++ gerados das declarações do DEX original, incluindo retorno `jlong` de
`nativeInit`, com checagem NDK adicionada ao build. Esses tipos não implementam
serviços nem tornam o shell carregável. Ver `horizon/ui/STARTUP-BRIDGE.md`.

O próximo alvo de análise é a inicialização da plataforma e a iteração de frame,
não empacotar um launcher substituto. A exigência de APK comum continua sujeita
aos bloqueios de serviços/permissões listados acima; não há garantia técnica de
portar integralmente o Horizon nesse regime.

## Execução do cliente original — 2026-10-01

Já há instalação e tentativa de inicialização do APK original, não apenas análise
estática. **Ainda não há UI original funcionando nem APK METAPORT publicável.**

| Experimento | Resultado real do aplicativo |
|---|---|
| Original sem alterações, run 36891774927 | Instalou; encerrou em `ShellApplication.<clinit>`: faltava `libhzos_spaces.meta.so` |
| Originais + 74 bibliotecas, run 36893813190 | Instalou; encerrou por falta de `libstatssocket.so` |
| Originais + 77 bibliotecas, run 36894922933 | Instalou; SIGILL durante inicialização de `libc++.so`, PC relativo `0x89660`, `std::__1::locale::id::__init()` |

O último pacote não deixou nomes DT_NEEDED pendentes no grafo percorrido. Isso
**não comprova compatibilidade de símbolos, namespaces, serviços ou hardware**.
Os arquivos originais do APK foram preservados byte a byte, exceto os metadados de
assinatura; a assinatura foi substituída por certificado próprio de teste, nunca
pela identidade da Meta. Foram usados componentes originais dos APEX ART, statsd
e runtime, sem stubs. APKs/chaves não foram publicados.

Ambiente: API 35 x86_64 com `libndk_translation.so`, aplicativo sem privilégios,
rede restrita a loopback, sem contato com servidores Meta. Após 20 segundos o
processo estava ausente. O SIGILL observado nesse ambiente não estabelece a causa
nem prevê sozinho o resultado em ARM64 físico. A próxima coleta inclui janelas
verificadas de instruções nos PCs do crash, sem alterar o código original.

Evidências: `analysis/android-runtime/original-shell-{baseline,bundled-baseline}.json`
e `original-shell-dependency-bundle.json`. Os relatórios de última execução podem
ser atualizados por CI; consultar também `run_id`/`source_commit` e o histórico Git.
Workflow verde significa coleta concluída, não boot funcional nem “90% Horizon”.

### Atualização do bloqueio da beta

Run **36919477652**: mesmo após a adaptação explícita de 206 pontos inventariados
em `libc++.so`, o aplicativo encerrou antes da UI. O próximo SIGILL está em
`libutils.so / android::SharedBuffer::attemptEdit()`, ELF `0xf860`, leitura RCpc
de **32 bits**. Os testes isolados de byte/64 bits não validam essa variante.
Não há APK de beta funcional nem validação no Infinix. Não apresentar a instalação
bem-sucedida ou o workflow verde como liberação pronta para hoje.

A análise original revelou um cliente local com Surfaces e roteamento de toque
para `emuNativeClick`, mas ele ainda não foi habilitado/validado no port e depende
da integração do serviço nativo. Nome e ícone do usuário continuam preparados;
não foram usados para mascarar esse bloqueio com uma Activity substituta.

Run **36924213557**: a alternativa de acquire de 32 bits passou no teste
independente, incluindo extensão para 64 bits; RCpc de 32 bits falhou no tradutor.
Todos os pré-requisitos de instruções passaram antes de instalar o original.
O aplicativo ultrapassou `attemptEdit`, mas encerrou em `SharedBuffer::release`
(próximo LDAPR em `0x10058`). Continua sem UI e sem beta funcional.
A experiência seguinte usa 14 pontos explícitos de `libutils.so`; não confundir
essa adaptação para o emulador com otimização para o Infinix ou para sua NPU.

Runs **36925786582** and **36939212398** still ended before original UI rendering:
first at the HIDL constructor, then at the JSON-value constructor in `libnblog.so`.
The explicit experimental policy now has 477 sites across 18 firmware libraries;
this count measures instruction adaptations for the CI translator, **not port
completion**. Run 36940043323 tests the latest policy; its result was pending at
this documentation update. Original APK DEX/resources remain unchanged.

Recovery 36939409546 also confirmed the real `privateipc.updater` package for
ShellNativeUpdaterHolder and the boot config's PreferencesManager/Spatial Window
Manager role dependencies. They have not been replaced by working app-scoped
services. There is still no functional beta, phone validation, or NPU inference.

Run **36940043323** completed with another pre-UI crash, now in
`libprocessgroup.so` at guest block `0x50460`. Its expanded census supplies 120
additional explicit sites across 11 firmware libraries. The next policy has
597 sites / 29 libraries. This remains a CI-only compatibility experiment,
not an installable functional demo or a port of the missing Java/native services.

Run **36940917880** reached the Java application constructor and crashed with
`NoClassDefFoundError: horizonos.graphics.Vector4f`, rather than the previous
SIGILL. The next opt-in experiment attempts to add original framework DEX from
the pinned hzos-framework JAR, with collision/namespace/checksum checks and no
rewriting of existing APK members. It is not a fabricated Vector4f implementation
or a working service bridge. Still no original UI, functional beta or phone test.

### Original framework dependency: current frontier

Vector4f is defined by the pinned original `hzos-framework.jar` (2041 classes;
SHA-256 b1c5111bb301daf971b658414daf8e43a0b4cdac9ecc2e94a554d0c861607e42).
Runs 36942634549 / 36943056110 / 36943586300 did not reach application execution:
they exposed internal DEX checksum differences and mixed Android namespace
classes in that JAR. The latest experiment selects non-boot original definitions
with dexlib2 and requires equal canonical baksmali output before appending them.
This reserializes DEX indices/layout; derived framework bytes are not identical.
Existing APK DEX/resources are still preserved, and no services are registered.

Run **36944360086**, source **6b5f0fb**, was last observed after successful host-tool
setup/compilation and during original input preparation. Its final outcome is
**unknown**: subsequent GitHub queries failed with HTTP 401 and authenticated Git
access stopped working. The GitHub connection in Arena needs reconnection before
remote outcomes or further pushes can be confirmed. No functional beta, original
UI rendering, physical-phone validation or NPU inference is established.

## Estado atualizado da inicialização — alinhamento DEX corrigido

Os registros anteriores de autenticação interrompida foram superados: leitura,
commit/push e testes Actions voltaram a funcionar. Run **36952973469** identificou
a rejeição real do DEX adicional: metadados hidden-API sem alinhamento de quatro
bytes. A correção preserva os flags originais e passou no run **36953764788**:
dexopt `PERFORMED`, inicialização além de `Vector4f`, mas novo crash por ausência
de `com.oculus.os.ActivityManagerUtils`. O teste seguinte inclui o segundo JAR
original fixado por hash, sem substituir classes do Android ou classes existentes.
Há também chamadas privadas negadas pelo Android; serviços e permissões não são
resolvidos simplesmente adicionando JARs. **Ainda não há beta funcional, UI
original validada, inferência NPU ou teste no Infinix.**

### Fronteira atual após os dois frameworks

Run **36954885176**: 2.820 classes originais selecionadas com igualdade canônica
(1.940 hzos + 880 plataforma Oculus). Os dois erros de classe ausente anteriores
foram superados. O crash atual ocorre no construtor de `IServiceCallback.Stub`,
chamado por `BinderClient`/`VrFocusManager`; o log confirma bloqueio de API privada,
não simplesmente ausência de um JAR. É necessária adaptação real do vínculo com
os serviços, sem desativar a proteção do Android ou fingir serviço disponível.
O coletor passa a preservar os contratos originais dessa fronteira para essa
adaptação. Não houve renderização original nem validação física.

### Transporte sem privilégios e bloqueio confirmado

A adaptação explícita de descoberta/callbacks Binder foi compilada e empacotada,
com apenas duas classes SDK alteradas e comparação exata das substituições
permitidas. O APK original continua sem alterações em seus DEX/recursos; o DEX
SDK adaptado é declarado separadamente. Run **37003660349** passou dez testes
instrumentados em cada API29/API35, inclusive callback com thread principal
bloqueada. Isso não valida execução da UI original.

Run **37003661090** confirma **ANR**: o construtor de ShellApplication espera
indefinidamente o provedor real de `vrfocus` ao registrar o listener de atividade.
O processo é encerrado pelo Android. A recuperação do servidor original foi
ampliada para permitir adaptar sua lógica, sem publicar um binder vazio, fingir
foco ou conceder permissões fictícias. **APK funcional ainda não obtido.**

### Recuperação nativa e primeira lógica executável do serviço de foco

Run **37007778951** decompilou as 455 funções identificadas no servidor nativo e
110 na interface Binder, com proveniência e limites explícitos. Não significa
que o serviço foi recompilado ou que toda a lógica inferida esteja correta.
A cadeia nativa e as cinco dependências de sistema estão em
`horizon/ui/FOCUS-NATIVE.md`.

A lógica de estado de sessão começou a ser transposta para C++ testável,
preservando a verificação de PID, UID observado, estados internos 0/2,
deduplicação e os efeitos exigidos por eventos repetidos. Os testes ASan/UBSan e
TSan passaram; o novo componente ainda **não está ligado ao VrShell nem é um
provedor Binder**. Política completa de foco, backends de atividades/janelas e
permissões continuam pendentes. O último APK testado ainda termina em ANR;
**não existe beta funcional ou inferência de mãos/NPU validada nesta etapa**.
