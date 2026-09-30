# UI original, mãos e Joy-Cons — resultados e limites

## Estado real

**Port completo: NOT PORTED YET.** Não há UI original utilizável no telefone,
hand tracking original em execução, enumeração de Joy-Cons como controles Quest,
APK funcional ou teste de Store. Os resultados abaixo não substituem esses requisitos.

## Código implementado e compilado

`port/android/adapters` recebeu um backend de eventos Android para Joy-Cons,
com núcleo C++ thread-safe e ligação JNI:

- identificação por VID/PID Nintendo L/R, sem adivinhar pelo nome;
- eventos reais de botões e sticks anunciados pelo driver Android;
- deadzone, normalização, remapeamento explícito e distinção de relógios;
- detecção de adição/mudança/remoção, proteção contra substituição silenciosa;
- liberação de botões em disconnect/pause e preservação de taps entre leituras;
- escolha solicitada Joy-Cons → mãos quando nenhum Joy-Con reconhecido permanece.

`HANDS_REQUESTED` é uma solicitação de fonte, **não execução de um provider de mãos**.
O provider original permanece explicitamente ausente. Posição e orientação dos
Joy-Cons permanecem inválidas; não foi inventado tracking 6DOF a partir de botões/IMU.
A semântica de ações do módulo é interna, não um layout privado do Horizon.

Actions **36727215685**, fonte `4c8ce68`: AAR ARM64 compilado, 7 testes Java sem falhas,
lint e validação de segmentos ELF 16 KiB passaram. Os testes nativos com ASan/UBSan
cobrem seleção de fonte, desconexão, timestamps, valores inválidos e concorrência.
Não houve pareamento nem teste de sensores de um Joy-Con/telefone físico.

## Decompilação da UI

JADX **1.5.6**, distribuição oficial com SHA-256 fixado no workflow. Último ensaio
**36728364524**, fonte `2dd150e`; não executa nem instala os APKs.

| Original | Saída Java reconstruída | Arquivos com marcadores de erro | Erros totais relatados pelo JADX |
|---|---:|---:|---:|
| VrShell | 8.013 arquivos | 35 | 148 |
| MetaSystemUI | 3.143 arquivos | 10 | 23 |

Arquivos sem marcador de erro também **não estão semanticamente validados**. Nomes,
tipos e fluxo reconstruídos não equivalem à fonte original ou a código recompilável.
O fluxo tentou todos os DEX dos dois APKs; não decompilou todos os componentes do OS.
Os arquivos Java completos ficam temporariamente no runner. Git recebe evidências
limitadas, hashes, dependências, assinaturas e trechos dos call sites.

Foi inspecionado também `libshell.so` original, SHA-256
`2d4c274bc81c9f545f3b5571ba57643a9696333e8f6b3a125e45682fbd96dce0`.
Entre as dependências reais: `libhzos.meta.so`, `libhzos_spaces.meta.so`,
`libopenxr_loader.so`, EGL/GLES, Binder NDK, FMOD e serviços internos. Substituir
somente a Activity não fornece esses serviços nem um compositor funcional.

### Entrada genérica encontrada na UI

O call site original em `X/C0Dl.java` passa para
`ShellApplication.nativeJoypadAxis(FFFFFFI)V` os eixos Android **0, 1, 11, 14, 17, 18**,
seguidos de `MotionEvent.getDeviceId()`, sob uma checagem `isAlive()` do Shell.
Isso documenta **entrada de gamepad genérico**, não enumeração de controles Quest.
O Y original é repassado no domínio Android; o Y semântico do adapter MetaPort foi
invertido e não pode ser encaminhado sem conversão.

`nativeKeyEvent(IIIIZZZZ)V` e notificações de adição/remoção de dispositivos também
foram encontradas. A semântica completa dos argumentos de tecla não foi recuperada.
O contrato observado e sua ligação ao relatório estão em
`horizon/input/original-contract.json`, com teste de regressão contra a evidência.

## Decompilação nativa de mãos

A seleção inicial por nomes exportados falhou em encontrar funções de mãos:
`libtrackingengines.so` só exporta três símbolos de registro de capacidades.
O ensaio 36724585535 produziu **zero funções decompiladas**; não foi tratado como
recuperação do algoritmo. Também houve timeout da análise automática e avisos de
relocação TLS não resolvida.

A versão corrigida usa o registro de capacidades, referências a strings de mãos
e o image base do Ghidra para converter corretamente os endereços ELF.
Ensaio **36727073533**, fonte `2432ded`, Ghidra **11.3.2** com hash fixado:

- **24 funções** de `libtrackingengines.so` reconstruídas em C-like;
- **24 funções** de `libtrackingserviceclients.so` reconstruídas em C-like;
- seleção por referência inclui `HandTrackingApi`, `HandTrackingSensors`,
  `HandTrackingInterface`, `HandTrackingEngine` e `NIMBLE:DPE_HandTracker`;
- relatórios mantêm o estado **DECOMPILED_NOT_VALIDATED**, endereços ELF, image base,
  motivos da seleção e avisos. Não são headers ABI prontos nem funções executadas.

Achados concretos desta versão:

- `capabilityRegistryGetAbiVersion` retorna **0x24 / 36**; `CreateV3` compara esse valor.
- `createHandTrackerFbs` seleciona versões **11 a 14**; isso não descreve ainda seus
  métodos virtuais, payloads ou ownership.
- `createInputInjectionFbs` e `createControllerTrackingFbs` verificam versão **1**.
- `createControllersFbs` possui casos **2 a 7**, com retornos/layouts diferentes.
  Não usar o tamanho de uma alocação como se fosse uma definição pública da ABI.

O manifesto original declara `IHandTrackingService`, `IControllerTrackingService`,
`IInputDataInjection` e as interfaces `horizonos.perception.handtracking`.
Existência desses serviços **não prova** permissão, implementação operante ou payload
compatível com o adapter Android.

## Modelos e esqueletos originais

Os containers TorchScript foram inspecionados com `pickletools`, **sem unpickle,
importação ou execução**. Há referências ao backend privado **BoltNN**. A biblioteca
contém também strings de ExecuTorch, kernels CPU/XNNPACK e integração Hexagon. A
presença dessas strings não prova que cada modelo tem fallback CPU ou funciona no
MediaTek do Infinix. Os arquivos `etz0` continuam opacos, não decodificados.

MessagePack foi decodificado estruturalmente, com limites:

- rigs FBX L/R contêm **79 bones**, incluindo marcadores;
- rest skeletons contêm **19 bones** e **22 entradas de juntas/limites** por lado;
- esses números não são uma definição do layout de saída OpenXR nem autorização
  para copiar arrays entre APIs. Unidades e convenções de poses não foram validadas.

## Próximos bloqueios de integração

1. Recuperar callbacks/vtables, payloads e lifecycle do registro/clients originais;
   não chamar C++ privado com structs inferidos por tentativa.
2. Adaptar aquisição e calibração de câmera do telefone ao contrato real do engine,
   incluindo arbitragem com ARCore e sincronização de relógios.
3. Validar execução do modelo/backend e condições de tracking inválido/perdido.
4. Implementar o transporte host↔guest e a integração com os consumidores originais;
   entrada de gamepad da UI não basta para tracking/enumeration Quest.
5. Resolver userdata/criptografia, gráficos e demais HALs que ainda impedem o boot
   completo e a execução da UI. SELinux não foi desligado.

Nenhuma interface foi substituída por um serviço falso que retorna sucesso.
Nenhum arquivo foi gravado no telefone e nenhum servidor Meta foi contatado.
