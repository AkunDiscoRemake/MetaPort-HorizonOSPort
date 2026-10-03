# Hand tracking: geometria original, preparação visual e animação

**Hand tracking completo, animação integrada e renderização Horizon no telefone:
NOT PORTED YET.** Este trabalho não gera poses falsas, não desenha uma interface
substituta e não transforma uma biblioteca de poses em animações inventadas.

## Implementado e medido com os arquivos originais

- `handtracking/ai/hand_assets.py`: leitura MessagePack limitada, sem executar
  modelos, com rejeição de chaves duplicadas, extensões e números não finitos.
- A imagem ODM é verificada contra a reconstrução; os quatro arquivos são
  conferidos por tamanho e SHA-256 em `hand-assets-policy.json` antes da leitura.
- Preparação das malhas esquerda/direita em buffers indexados. A chave de
  reutilização é **identidade do vértice original + índice UV**, não proximidade
  espacial: não se soldam vértices com skinning diferente nem costuras UV.
- Ordem e orientação de cada triângulo preservadas; polígonos não triangulares
  são recusados, em vez de triangulados por uma regra não comprovada.
- Posições, normais, UVs e pesos só são gravados como float32 se o valor puder ser
  representado **exatamente**. Nenhuma normalização, quantização ou poda de pesos.
- Paleta compacta contém apenas índices realmente referenciados pelos pesos,
  mantendo um mapa inverso para a hierarquia original completa.
- Validador independente decodifica os buffers e compara **todos os cantos dos
  triângulos e todas as influências**, incluindo a identidade de origem.

Resultados do run [36777260117](https://github.com/AkunDiscoRemake/MetaPort-HorizonOSPort/actions/runs/36777260117),
source `5e88321`, em `hand-assets-report.json`:

| Dado, por mão | Resultado |
|---|---:|
| Vértices de origem | 1.159 |
| Vértices de desenho, incluindo costuras UV | 1.360 |
| Triângulos | 2.314 |
| Cantos/índices | 6.942 |
| Índices de desenho | 16 bits |
| Nós na hierarquia original | 79 |
| Nós referenciados na paleta de skinning | 17 |
| Influências preservadas | 2.981 |
| Máximo de influências por vértice | **7** |
| Fluxo de vértices sem indexação, referência de comparação | 222.144 bytes |
| Fluxo de vértices preparado | 43.520 bytes |
| Todos os seis fluxos preparados | 91.400 bytes |

Os 91.400 bytes incluem vértices, índices, identidade de origem, offsets CSR,
pesos e paleta. **Não** incluem o sistema inteiro, materiais, texturas, biblioteca
de poses, transformações de repouso ou buffers transitórios de execução.

A redução de aproximadamente 80,4% refere-se **somente ao fluxo de vértices em
comparação com uma expansão sem índices**, não a FPS, latência ou memória total
do Horizon. Os dois arquivos passaram pela comparação integral dos buffers.

Há 40 vértices com cinco influências, 12 com seis e dois com sete, em cada mão.
Uma conversão automática para quatro influências perderia informação original.
O maior desvio das somas de pesos em relação a 1 é cerca de `4,10e-8`; os valores
originais foram mantidos, não corrigidos silenciosamente.

## Código nativo para a futura transferência de poses

`port/android/adapters/src/main/cpp/hand_palette.{hpp,cpp}` implementa `PalettePlan`:

- valida e pré-calcula a seleção na carga do asset;
- combina seleções consecutivas em blocos de cópia;
- não aloca memória no caminho de transferência por frame;
- preserva os bytes dos registros fornecidos pelo chamador;
- recusa buffers insuficientes, sobreposição e paleta inválida antes de escrever;
- invalida configuração antiga quando uma nova configuração falha.

A classe não gera poses, não conhece a ABI original, não decide a ordem de
quaternions nem assume matrizes 3x4/4x4. O tamanho de registro é explícito.
Ela precisa receber dados válidos de uma **bridge original ainda não implementada**.
Não há conexão JNI ou renderer de mãos pronta. O código foi incluído no build C++
do AAR. Run [36777379110](https://github.com/AkunDiscoRemake/MetaPort-HorizonOSPort/actions/runs/36777379110),
source `19a3ce3`, concluiu build Android ARM64, testes nativos com sanitizadores,
sete testes Java e lint. `analysis/android-build/build-report.json` registra
`gradle_exit_code=0`, mas também `horizon_integration=NOT PORTED YET` e ausência
de teste físico. Um AAR compilado não é um APK Horizon funcional.

O teste nativo usa AddressSanitizer/UBSan e compara todos os 255 subconjuntos não
vazios de uma hierarquia de oito registros, em quatro tamanhos de registro, além
de casos de erro e sobreposição. Isso valida a cópia, não o tracking.

## O que foi recuperado sobre poses — sem inventar animações

`defaultProfile.msgpack` contém 433 entradas, cada uma com 22 canais. Os nomes
identificam movimentos de polegar/dedos e punho. Isso **não estabelece timeline,
FPS, interpolação, seleção de gesto ou que esses dados sejam clips de animação**.

Os arquivos de repouso possuem duas coleções com 19 bones e 22 joints/limites.
As malhas FBX possuem 79 nós, inclusive marcadores; suas raízes são o punho e um
nó da malha. Seus registros de repouso contêm o campo `Rot`, e a ordem declarada
é `XYZ`. Nenhum desses fatos autoriza tratar os espaços de 19, 22, 79 e 17 índices
como equivalentes ou escolher uma convenção de quaternion por suposição.

A análise nativa foi ampliada para procurar consumidores de `PreRotation`,
`TranslationOffset`, `RestState`, `SkinningWeights` e arquivos `defaultfbx`, além
da preparação de tensores. A decompilação é evidência estática, não uma assinatura
C++ válida ou animação já portada.

## Caminho visual encontrado no VrShell original

Run [36778223318](https://github.com/AkunDiscoRemake/MetaPort-HorizonOSPort/actions/runs/36778223318)
inspecionou o APK verificado. O relatório `hand-presentation-report.json` localizou
em `libshell.so` (SHA-256
`2d4c274bc81c9f545f3b5571ba57643a9696333e8f6b3a125e45682fbd96dce0`):

- referências a `xrCreateHandTrackerEXT`, `xrLocateHandJointsEXT`,
  `xrDestroyHandTrackerEXT` e `xrGetHandMeshFB`;
- nomes das extensões de tracking, mesh, aim, motion range, data source e
  microgestures; a presença dos nomes não comprova suporte no telefone;
- `CoHandRenderBehavior`, `IHandRenderingSystem`, `HandRenderingSystem` e
  `GhostHandRenderingSystem`, com caminhos de arquivos-fonte compilados;
- parâmetros `ShellHandMaterial.u_opacityRange` e `ShellHandMaterial.u_alphaFade`;
- mensagens de erro de aquisição de mesh e quantidade inesperada de joints.

**Consequência importante:** não está estabelecido que as malhas FBX de tracking
preparadas acima sejam exatamente as malhas que o VrShell recebe por OpenXR.
Não se deve substituí-las silenciosamente nem declarar seu renderer portado.
A identificação do caminho OpenXR orienta a próxima bridge e a recuperação das
regras originais de apresentação, opacidade e transições.

Nenhum membro ZIP casou com o filtro de nomes de recursos de mãos/shaders/animacões.
Isso não prova ausência desses recursos: podem estar embutidos, ter outros nomes
ou vir de componentes externos. `libovravatar2p.so` também contém contratos de
skeleton/pose de mãos customizados, que não foram confundidos com tracking real.

`prepare_hand_render.py` agora prepara apenas o renderer de hash fixo para
Ghidra e converte offsets de arquivo em VAs ELF através dos segmentos PT_LOAD,
sem somar o image base duas vezes. A primeira decompilação específica do renderer concluiu com 22 funções;
[fluxos recuperados e limites do decompilador](HAND-RENDERER-TRACE.md).
Isso ainda não é renderer executável nem reprodução validada das animações.

### Recuperação nativa mais completa, sem ocultar falha de validação

Run 36777058920 produziu 32 funções de entrada e quatro consumidores visuais
(`hand-input-visuals.json`). A análise automática ainda atingiu o limite de 900 s,
portanto não é análise completa. Contudo, os corpos do listing já contêm centenas
ou milhares de bytes e chamadas reais, em vez dos corpos de um endereço da
passagem anterior. `FUN_008b9ce0` lê campos de geometria/skinning; `FUN_00ade360`
referencia a biblioteca de poses; as outras duas funções referenciam RotationOrder.

O antigo teste do workflow rejeita esse relatório porque exige uma descrição
textual de candidato sem DataReference, enquanto a nova passagem recuperou as
DataReferences. O novo validador usa identidade/endereço e correspondência aos
candidatos de ponteiro, não esse texto. Validou localmente o relatório real:
32 funções e nove candidatos de ponteiro decompilados. A conclusão histórica do
run permanece **failure**, não foi reescrita como sucesso.

Outro cuidado: a função encontrada por `use_uint8_input` que exige uint8 inclui
`BodyTrackingEncoderTorchModel loaded`. Isso não autoriza mudar o atributo false
do DPE de mãos. A seleção seguinte prioriza callers diretos dos construtores de
mãos antes de referências genéricas de quantização/outros modelos.

## Bloqueios restantes e critérios de integração

1. Confirmar fórmulas de preparação das imagens, extrínsecas, unidades e validade
   dos dados de câmera; não duplicar imagens para fingir câmeras Quest.
2. Executar os modelos originais num backend compatível. Os PTE usam
   `HexagonRpcBackend`; os PTL inspecionados também referenciam o backend privado
   `boltnn`. A presença de operações aten/XNNPACK não prova um fallback CPU completo.
3. Recuperar ownership, timestamps e ABI do produtor de poses original.
4. Recuperar mapeamento entre canais, esqueleto de repouso e nós de skinning,
   incluindo convenções e inversas de bind; não presumir LBS/DQS como algoritmo original.
5. Integrar materiais, shaders, oclusão, seleção de gestos e transições no renderer
   original, sem substituir isso por um desenho demonstrativo.
6. Medir erro de tracking, estabilidade, latência, GPU/CPU, temperatura e consumo
   **no Infinix X6873**, com testes de duração. Ainda não houve teste físico.

Os buffers derivados ficam em `local-analysis/` no runner e não são publicados
no Git nem nos artefatos do workflow. São publicados apenas hashes, contagens,
metadados limitados e resultados de validação. A GPLv3 do código MetaPort não
relicencia os assets originais.
