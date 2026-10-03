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

## Comunicação Binder de foco — 2026-10-02

Implementado o endpoint das onze operações de `IVrFocusService`, com formatos
`ClientStatus`/`ImmersiveApp` e callbacks one-way cruzados com os contratos Java e
nativos recuperados. Captura PID/UID real do Binder, exige backend completo e
verificação de acesso; entradas inválidas são rejeitadas antes de operar o estado.
Não define classes substitutas em `oculus.internal`, não publica um serviço vazio
e não declara foco/poses/permissões que o sistema não forneceu.

- Build Android `37021606190`: passou.
- Verificações do projeto e sanitizers nativos `37021605969`: passaram.
- Instrumentação `37021605827`: **16 casos próprios passaram em cada API 29/35**,
  incluindo quatro casos de protocolo; backend de teste explicitamente limitado
  aos fixtures, não apresentado como política de foco.

Ainda falta implementar a política e a posse/morte dos listeners, conectar os
backends reais, verificar interoperabilidade com o proxy original e publicar o
serviço antes do construtor de ShellApplication. O novo endpoint não é incluído
no APK original nessa etapa. O bloqueio de inicialização continua sem solução e
**não há APK original funcional**. Detalhes: `horizon/ui/FOCUS-NATIVE.md`.

## Posse e encerramento de listeners — 2026-10-03

`FocusListeners` agora registra listeners por PID/tipo com UID real, conserva
registros duplicados, remove o grupo do chamador no cancelamento e observa morte
real de Binder. As chamadas aos clientes ocorrem sem segurar a trava do registro;
falha de um cliente não interrompe os demais. Não há callback inicial inventado.
O argumento de `onVrFocusChanged` é o **tipo alterado (0/1)**, não uma concessão de
foco — comportamento recuperado do método nativo `notifyListeners`.

- Build Android `37120394700`: passou.
- Verificações do projeto/nativas `37120394643`: passaram.
- Instrumentação `37120394692`: **21 casos próprios por API 29/35 passaram**,
  incluindo limpeza após morte real de um processo Android separado, apenas no
  APK de teste do emulador. Nenhum processo do usuário é encerrado.

Limites e diferenças intencionais do daemon estão em `horizon/ui/FOCUS-NATIVE.md`.
A política de foco ainda não está implementada/conectada; o registro exige uma
política de acesso fornecida pelo serviço e não concede permissões por padrão.
Este componente não publica `vrfocus` nem elimina a espera do construtor original.
**Ainda não há APK original funcional.**

## Núcleo de decisão de foco — 2026-10-03

Implementado `focus_decision.hpp`: combina as fontes originais de clientes,
separa os tipos 0/1, aplica a prioridade do aplicativo imersivo/foco do display e
só depois o acesso autorizado em segundo plano. Preserva identidade UID/PID,
ordenação, deduplicação e resultados negativos. Não habilita modo permissivo.

O run `37121195806` confirmou os destinos exatos da vtable original: as entradas
5/6 são `getClientsWithTopActivities` e `getAllClientsWithTopActivities`, não
fontes intercambiáveis. O código e os testes agora usam esses vínculos comprovados
estaticamente. Corrigido também o nome do argumento de grant/revoke de rastreamento:
é **displayId**, não PID; isso não altera o protocolo nem concede acesso.

- Suíte nativa local: **15 casos passaram**, incluindo o novo núcleo sob
  ASan/UBSan e TSan; nenhum binário original foi executado nesses testes.
- Projeto/sanitizers no CI `37121443278`: passou.
- Build Android `37121443238`: passou.
- Regressão Android `37121443260`: **21 casos próprios por API 29/35 passaram**.
  Esses testes Android não exercitam o novo núcleo C++ nem a política Meta original.

O núcleo exige snapshots completos e metadados já resolvidos/autorizados; não
consulta serviços privados, não inventa observações ausentes e não aplica sozinho
as alterações de estado do ClientManager. Ainda faltam seleção/histórico do app
imersivo, produtores reais dos dados e integração do serviço antes do construtor
original. **O bloqueio de inicialização permanece; não há APK original funcional.**

## Seleção imersiva ligada ao núcleo de foco — 2026-10-03

Fonte **d87e1a5** implementa `focus_immersive.hpp/.cpp`: prioridades de seleção
recuperadas do daemon, resolução do cliente superior, lookup ordenado do shell
e histórico diagnóstico de dez entradas. O coordenador usa a seleção para
alimentar o núcleo de decisão, sem aceitar um PID imersivo externo obsoleto.
A implementação compilada é compartilhada entre o alvo Android e os testes
nativos. Oito funções recuperadas e instruções ARM64 específicas sustentam os
contratos; detalhes e limites em `horizon/ui/FOCUS-NATIVE.md`.

Validação concluída:
- Projeto/regressão/nativo **37122883668**, sucesso; **17 casos nativos** com
  ASan/UBSan/TSan, incluindo seleção, histórico e concorrência.
- Build Android **37122883654**, sucesso, incluindo compilação NDK arm64 da
  implementação e testes Java/lint.
- Runtime dos adaptadores **37122883673**, sucesso: **21 testes próprios por
  API 29 e 35**, em x86_64. Não executam o novo coordenador C++ nem o daemon
  original; não são validação do Horizon ou do Infinix.

**Ainda não há APK original funcional.** O seletor consome observações explícitas
coerentes; não as coleta do Android. Faltam o backend real de metadados/permissões,
o bookkeeping de ganho/perda de foco, a ligação Binder/JNI e a publicação antes
da construção de Application. O ANR original não foi resolvido nesta alteração;
não foi publicado serviço vazio nem inventado estado de foco/rastreamento.

## Ganho/perda de foco por cliente — 2026-10-03

Fonte **d4de4df** implementa o bookkeeping recuperado de `addCurrentFocus`
(`0x12bc0`) e `removeCurrentFocus` (`0x12de0`), agora aplicado pelo coordenador
nativo a cada linha de decisão. O cache usa PID com conferência de UID;
operações repetidas são idempotentes e os dois tipos permanecem independentes.
O estado de foco não altera permissões. Cadastros não são criados por consultas:
instalação/invalidação explícitas ainda precisam vir do backend real de metadados
e ciclo de vida de processos. Reinstalação de um registro limpa seu foco antigo.

Validação da fonte:
- Projeto/nativo **37124230529**, sucesso; **19 casos com sanitizadores**, incluindo
  estado, UID divergente, substituição/reuso, decisões repetidas e concorrência.
- Build Android ARM64 **37124230516**, sucesso.
- Runtime dos adaptadores **37124230539**, sucesso, **21 testes próprios em cada
  API 29 e 35**. Não executa o novo ledger/coordenador nem firmware original.

Isso substitui a pendência de implementação das mutações do conjunto de foco,
não a pendência de integração com o ClientManager/backend Android real. Ainda
faltam observações coerentes, metadados/permissões, ponte Binder/JNI e publicação
pré-Application. **O ANR original permanece; não há APK funcional com Horizon
original nem validação física no Infinix.**

## Metadados reais do próprio processo Android — 2026-10-03

Fonte **d27c633** adiciona `AppProcessMetadataBackend`: PID/UID reais, nome do
processo fornecido pelo Android, pacote da aplicação, pacotes associados ao UID
e verificações reais das duas permissões de background identificadas no daemon.
Não há concessão automática: os resultados de permissão são valores brutos do
Android, não autorização Meta nem grants enviados ao núcleo. Metadados ausentes
e divergência entre pacote/UID falham explicitamente. A leitura é limitada ao
próprio processo, sem consulta a PID arbitrário; não é um observador global.

Validação concluída da fonte:
- Projeto/regressão/nativo **37125874985**, sucesso.
- Build Android ARM64 **37125874981**, sucesso.
- Runtime **37125874971**, sucesso: **24 testes próprios por API 29 e 35**,
  incluindo três novos casos para identidade/pacotes, resultados de permissão
  e rejeição de contexto incompatível. A execução é de adaptadores próprios,
  não do firmware original ou do Infinix.

O leitor ainda não está ligado ao coordenador C++/Binder. Seu nome de processo
Android não foi equiparado sem prova ao helper privado original. Também exige
Context, portanto não resolve sozinho a publicação pré-Application. Faltam o
cache/lifecycle completo de metadados, composição coerente das entradas de foco
e bootstrap do serviço. **Ainda não há APK original funcional; o ANR de espera
pelo serviço de foco permanece.**

## Registro real de identidade Android no núcleo nativo — 2026-10-03

Fonte **304f8fb** liga a identidade observada por `AppProcessMetadataBackend` ao
registro de cliente do `FocusPolicyCore` via `NativeFocusClient`. O JNI confere
novamente PID/UID usando `getpid/getuid`, usa tokens opacos não reutilizados,
limita instâncias a 32 e protege lookup/destruição contra concorrência. Fechar é
idempotente; atualizar observações não reinstala nem limpa o registro. Regras de
consumo preservam nomes JNI ao aplicar shrinking em aplicativos consumidores.

Validação da fonte:
- Projeto/regressão/nativo **37129323107**, sucesso.
- Build Android ARM64 **37129323137**, sucesso.
- Runtime **37129323142**, sucesso: **28 testes próprios em cada API 29 e 35**,
  incluindo execução JNI real de cadastro/consulta, rejeição de identidade
  adulterada/tokens obsoletos, fechamento concorrente e limite/recuperação de
  capacidade. Os runs anteriores da fonte e82ee6c foram substituídos; não são
  utilizados como evidência final.

A ligação transporta **identidade**, não converte permissões em grants nem nomes
Android em metadados normalizados. Cada instância possui seu próprio núcleo;
não há provedor global. Os testes chamam registro/consulta do ledger nativo, mas
não a avaliação/seleção completa. Um conjunto inicial vazio não é exposto como
status de foco observado. Ainda faltam composição coerente das entradas,
conversão/cache/liveness completos, binding da avaliação e backend/publicação
Binder antes de Application. **Não há APK original funcional nem correção do
ANR original nesta alteração.**

## Avaliação completa do núcleo de foco pelo JNI — 2026-10-03

Fonte **4153a8b** liga seleção imersiva, decisão e bookkeeping do núcleo C++ ao
JNI, por um transporte interno validado e limitado (não é o Parcel ABI Meta).
Retorna aplicativo selecionado, nome superior, decisões ordenadas, histórico e
estado do próprio registro. Tipos ainda não consultados ficam explicitamente
**desconhecidos**, por uma máscara separada; não são tratados como perda de foco.
Consulta apenas de outros clientes não transforma o registro próprio inicial
em estado observado. Não há cadastro implícito nem concessão de permissões.

Validação da fonte:
- Projeto/regressão/nativo **37130802378**, sucesso; **20 casos com sanitizadores**.
  O decodificador inclui truncamentos, limites, UTF-8 e 10 mil mutações controladas.
- Build Android ARM64 **37130802346**, sucesso.
- Runtime **37130802416**, sucesso: **33 testes próprios em cada API 29 e 35**.
  Agora os testes executam a avaliação/seleção e o histórico C++ via JNI, além do
  registro. Verificam ambos os tipos, canais distintos, ordenação/deduplicação,
  precedência de background, entradas inválidas sem alteração do estado,
  Unicode e fechamento concorrente. A fonte anterior 9d6edd7 não é usada como
  validação final deste marco.

Os novos frames são **fixtures identificadas como tal**, não observações do
Horizon original nem grants reais. A API de avaliação é interna/package-private:
ainda não há produtor Android de todos os canais/metadados normalizados coerentes.
As observações próprias existentes não são substituídas por dados inventados.
Faltam composição/normalização/liveness completos, backend Binder e publicação
antes de Application. **O ANR original permanece, e ainda não há APK funcional
com a interface original nem validação no Infinix.**

## Núcleo anterior à Application e eventos de sessão via JNI — 2026-10-03

Fonte **fd9767b** permite criar o núcleo nativo com identidade real do próprio
processo **sem Context**. O leitor de metadados pode ser anexado depois, sem
reinstalar o registro ou apagar estado. Até isso acontecer, metadados continuam
explicitamente indisponíveis — nenhum pacote, permissão ou foco é presumido.

O JNI agora liga os eventos locais de serviço 0/2 ao reducer nativo existente,
com verificação de PID/UID e opção de preservar o Caller capturado pelo endpoint
antes de despacho assíncrono. O estado diferencia desconhecido de visível/parado,
preserva efeitos exigidos em eventos duplicados e não transforma esses eventos
em decisões de foco. Os efeitos ainda precisam de um consumidor de backend real.

Validação da fonte:
- Projeto/regressão/nativo **37131841181**, sucesso; 20 casos com sanitizadores.
- Build Android ARM64 **37131841135**, sucesso.
- Runtime **37131841147**, sucesso: **38 testes próprios em cada API 29 e 35**.
  O teste com AppComponentFactory confirmou identidade disponível no núcleo JNI
  **dentro do construtor da Application de teste, com base Context ainda nulo**.
  Também passaram anexação tardia, eventos/duplicatas, rejeição de identidade e
  fechamento/isolamento entre instâncias.

A factory/Application modificadas pertencem somente ao APK de instrumentação;
o manifesto da aplicação original não foi alterado nem foi publicado um serviço
Binder incompleto. A criação antecipada do núcleo está verificada, mas ainda
faltam produtor coerente completo, normalização/metadados/liveness, consumidor
de efeitos e backend/publicação do serviço original. **O ANR original permanece;
ainda não há APK funcional com Horizon original nem validação no Infinix.**

## Estado de sessão alimentando renderização/seleção — 2026-10-03

Fonte **d9fa72c** conecta a participação do próprio processo no estado de sessão
à entrada de clientes em renderização da seleção imersiva. A correspondência
foi confirmada no ARM64: getter e transições usam o conjunto +0x170. Nenhuma
atividade/janela/display/permissão é derivada desse estado.

A avaliação vinculada exige observação reconhecida, pertencente à mesma
instância, e confere sua geração sob o bloqueio nativo que protege atualizações.
Observações antigas, de outra instância ou metadados incompatíveis são rejeitados
antes de alterar a política. O formato interno distingue renderização delegada
de uma observação explicitamente vazia. As demais entradas continuam obrigatórias.
A regra original de seleção do shell permanece válida mesmo após parar rendering;
o evento sozinho não força perda de foco nem concede rastreamento.

Validação concluída:
- Projeto/regressão/nativo **37133198483**, sucesso; **21 casos com sanitizadores**.
- Build Android ARM64 **37133198509**, sucesso.
- Runtime **37133198738**, sucesso: **42 testes próprios por API 29 e 35**,
  incluindo a ligação sessão/seleção, rejeição de estado antigo/de outra instância,
  metadados ausentes/inconsistentes e concorrência exercitando o bloqueio nativo
  sem depender apenas do monitor Java.

Isso garante coerência do canal de sessão, não de todas as observações Android.
Os demais canais/metadados nos novos testes são fixtures explícitas. Ainda faltam
produtor completo de observações, normalização/metadados/liveness, execução dos
efeitos e backend/publicação Binder. **O ANR original permanece e ainda não há
APK funcional com Horizon original ou validação física no Infinix.**

## Janela Android real alimentando a avaliação nativa — 2026-10-03

Fonte **132d33b** liga callbacks/polls reais de `AppWindowFocusBackend` ao núcleo
C++ por `NativeWindowFocusInput`. A ligação confirma apenas janela focada do
próprio processo no display principal Android. Observador vazio, tardio ou fechado
mantém o canal desconhecido; não produz uma falsa observação de ausência global.
Sessão e janela têm fontes/gerações verificadas juntas sob o bloqueio nativo;
observações antigas e de fontes encerradas/substituídas não podem ser usadas.

Validação da fonte:
- Projeto/regressão/nativo **37134190221**, sucesso; **22 casos com sanitizadores**.
- Build Android ARM64 **37134190220**, sucesso.
- Runtime **37134190224**, sucesso: **45 testes próprios por API 29 e 35**.
  Os novos testes lançam uma Activity real, observam sua janela e executam a
  avaliação pelo JNI. Cobrem versões antigas, substituição/fechamento da fonte,
  início tardio, obrigação de thread principal e fechamento do cliente nativo.

O canal de janela desses testes é real. Os demais canais/metadados ainda não
integrados continuam fixtures declaradas, e não foi executado o Horizon original.
A ligação não deduz foco do display, estado XR, permissões ou foco de outros
processos. Faltam cobertura/observações completas, normalização/metadados/liveness,
consumo dos efeitos e backend/publicação Binder. **O ANR original permanece;
ainda não há APK funcional com interface original nem validação no Infinix.**

## Cache de metadados `ClientManager` e redutores de acesso/display — 2026-10-03

`focus_client_metadata.hpp` e `focus_display_access.hpp` portam para C++/JNI as
regras recuperadas de `/system_ext/bin/vrfocusserver`:
- `ClientManager` (`0xf0d0`, `0x10aa0`, `0x118e0`, `0x12bc0`, `0x12de0`, `0x13400`):
  desambiguação de pacote por UID único vs. múltiplos pacotes com prefixo antes
  de `':'` (`0x10dec..0x10f4c`), override `"system_server"` ->
  `"android.uid.system:1000"` (`0x10fdc..0x11084`), concessão de foco em segundo
  plano para `uid == 0`, permissões `ACCESS_BACKGROUND_{HEAD,INPUT}_TRACKING`,
  pacotes `com.oculus.{vrshell,guardian,systemdriver}` (`DAT_0013d1c8`) e daemons
  `/system/bin/audioserver`@1041 e `/system_ext/bin/mrsystemservice`@1000
  (`DAT_0013d1e0`), cache indexado por PID com invalidação em divergência de UID
  (`0x11af8`), atualização de `metadata_process_name` na cópia retornada em
  cache hit (`0x11a60`) e poda de processos mortos em `getSnapshot` (`0x13400`).
- `DisplayTrackingAccessState` (`0xf5e0`, `0x15480`, `0x182e0`, `0x1a4c0`,
  `0x20860`, `0x20cc0`, `0x21540..0x22660`, `0x22d50`, `0x265d0`, `0x2cb90`,
  `0x2ccc0`, `0x2dd60`): bypass de `checkCallingPermission` para `callingUid == 1041`
  (`AID_AUDIOSERVER`), estado inicial `main_display_focus_ = true` e
  `active_displays_ = {0}`, máscaras `2`/`0` de `IDisplayManager` nas transições
  `1 -> 2` e `2 -> 1`, `onDisplayEvent(id, 3)` revogando apenas displays
  secundários, vetor `foreground_activities_` (`+0x70`) preservando ordem de
  inserção para `getTopActivityClient` (`rbegin()`), `refreshImmersiveStates`
  (`0x1a4c0`), `maybeUpdateActivityState` (`0x22660`) e sincronização de
  `current_focus` no cache durante `evaluate_packet` (`0x25460`).
- A suíte nativa com sanitizadores (ASan/UBSan e TSan) passa a executar **26
  binários**, e a porta de instrumentação Android passa a exigir **49 testes
  próprios por API 29 e 35**.

## Backend `VrFocusService` (`0x29210..0x2dd60`) integrado ao `VrShell.apk` original (`com.oculus.vrshell`) — 2026-10-03

- `port/android/adapters/src/main/java/org/metaport/port/focus/VrFocusService.java`
  e `VrFocusBootstrap.java` integram `VrFocusEndpoint`, `FocusListeners`,
  `NativeFocusClient` e `NativeWindowFocusInput` implementando
  `VrFocusEndpoint.Backend` para as 11 transações Binder de
  `oculus.internal.IVrFocusService` (`0x29210..0x2dd60`), incluindo construção
  pré-`Application.onCreate()` (`createBeforeApplication`), publicação em
  `ServiceDirectory` (`"vrfocus"`), `ImmersiveApp("", 0, 0, false)` default em
  `notifyTopActivityListeners` (`0x2a7e0`) e `EX_NULL_POINTER` (`-4`) em
  `getImmersiveApp` quando ausente (`0x2c660`).
- `horizon/ui/service_transport.py` e `horizon/ui/bundle_shell_dependencies.py`
  empacotam `org.metaport.port.services.*` + `org.metaport.port.focus.**` em
  `classes4.dex` (SHA-256 `b527be94bb5b23e73c32425610df2761d7eb330bc89179d97f5069a3ff8d311c`)
  e compilam `lib/arm64-v8a/libmetaport_adapters.so` (SHA-256
  `e184c96150076554e9f5d0eb463087f1701465fcde18c3dbbece46633b7a00ff`, alinhamento
  ELF de 16 KiB) diretamente dentro do **`VrShell.apk` original (`com.oculus.vrshell`,
  `MetaPort-HorizonOS-v2.7-VrShell-Bundled-arm64.apk`, `103.055.501` bytes,
  SHA-256 `2c31f2fddbd7f507f73a4b9cbc9054a05e8f67fb450adc2f20f0a52d638b111e`)**,
  preservando `classes.dex`, `AndroidManifest.xml`, `resources.arsc` e todos os
  assets originais bit-a-bit (`compare_apks` verificado). O aplicativo substituto
  anterior (`org.metaport.horizonos`) foi removido do repositório e da release.
- Validação concluída:
  - Projeto/regressão/nativo **37153822661**, sucesso (**26 binários** C++ com ASan/UBSan e TSan).
  - Build Android ARM64 **37153822667**, sucesso (`metaport-android-adapters-arm64.aar`, SHA-256 `d278a29e94b45cc7c41fd1d873ecd7b7e10983f44e50bf07584ca167e1d13b2e`).
  - Runtime de adaptadores **37153822623**, sucesso (**49/49 testes** em API 29 e **49/49 testes** em API 35).
  - Probe offline do `VrShell.apk` original empacotado **37153822753** (`analysis/android-runtime/original-shell-rcpc-baseline.json`):
    - **O bloqueio anterior em `ShellApplication.<init>(:153)` (`VrFocusManager.registerVrTopActivityListener` -> `BinderClient.awaitService("vrfocus")`) foi integralmente superado!**
    - `ShellApplication.<init>()` concluiu e retornou sem ANR.
    - `ShellApplication.attachBaseContext(Context)` concluiu.
    - `Instrumentation.callApplicationOnCreate` entrou em `ShellApplication.onCreate()` e concluiu `SoLoader.init()` (`C44472Av.A00(this)`).
    - A fronteira de inicialização do `com.oculus.vrshell` original avançou para `ShellApplication.onCreate(:20)` -> `X.0bJ.A03(:28)` -> `com.oculus.os.PreferencesManager.getInteger(PreferencesManager.java:120)` -> `oculus.internal.PreferencesManagerInternal.getInteger(PreferencesManagerInternal.java:258)` -> `oculus.internal.osutils.BinderClient.awaitService`.


