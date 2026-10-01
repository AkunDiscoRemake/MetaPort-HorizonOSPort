# Otimizações do software ORIGINAL de mãos

**Inventário parcial. Não encontramos todas; port completo NÃO concluído.**
Não confundir as otimizações próprias de `hand_assets.py` / `PalettePlan` com
mecanismos encontrados no Horizon OS. Ganhos de FPS/latência no X6873 não medidos.

## 1. Evitar atualização redundante de valores de material — evidência direta

Origem: `libshell.so`, SHA-256
`2d4c274bc81c9f545f3b5571ba57643a9696333e8f6b3a125e45682fbd96dce0`.
Run 36781228984, `hand-render-decompilation.json`.

- Caller `FUN_00aba178` (GhostHandRenderingSystem) atualiza materiais de mão e contorno.
- Callee `FUN_00a428e4`, VA ELF `0x9428e4`, primeiro busca o parâmetro por hash,
  tamanho e comparação do nome. O hash sozinho não identifica o parâmetro.
- Com o parâmetro encontrado, o listing contém `fcmeq v0.4S,v0.4S,v1.4S` e duas
  reduções `uminp`. Se os quatro floats são iguais, não reescreve o valor nem
  marca esse objeto dirty nesse ramo. Se diferem, grava o valor e marca dirty.
- Isso comprova supressão de escrita/dirty redundante nesse caminho, **não**
  comprova que não ocorra nenhum upload de GPU por outros caminhos.

**Regra isolada portada em `hand_material.{hpp,cpp}`:** comparação SIMD ARM64
FCMEQ + duas reduções de mínimo, com referência escalar para testes no host.
Preserva igualdade de +0/-0, NaN não igual a si próprio e diferenças de um ULP.
Sem epsilon, clamp ou geração de confiança/pose. Sem alocações.

Não replica offsets privados, busca de nomes, sincronização, objeto de material,
renderer completo ou bridge JNI. O caller deve fornecer estado inicializado e
combinar o retorno com o dirty flag existente, nunca limpá-lo no ramo sem mudança.
Teste local ASan/UBSan passou; caminho ARM64 depende do build Android e ainda
precisa de execução/diferencial no dispositivo. Não é validação binária integral.

## 2. Reutilização de registro de binding — evidência estática

`FUN_00abad24` busca registro existente por nome e byte discriminador; retorna o
registro encontrado. Somente no caminho sem correspondência cria e insere outro.
Caller de ghost hands usa `sbSkinningMatrices`. O helper marca dirty antes da
busca: **não confundir com o ramo de supressão de dirty do item 1**.
Não há prova de zero-copy GPU, de ausência de alocações por frame ou do lifetime
privado do buffer. Não foi implementado cache que contorne esses contratos.

## 3. Inferência e representação numérica — comprovado / pendente

- Dez containers ETZ0 referenciam `HexagonRpcBackend`; relatório `ptez-report.json`.
  DPE apresenta duas instruções delegate, SKB uma, STP uma nos modelos analisados.
  Isso identifica delegação no programa, não mede execução ou latência de DSP.
- Metadados DPE incluem entrada Byte `[4,1,96,96]` e parâmetros de quantização;
  `use_uint8_input=false` pertence a outra camada. Não remover conversões nem
  normalizar pixels por adivinhação. `model-evidence-validation.json` preserva
  divergências ainda não resolvidas na leitura de atributos.
- Factory `FUN_0170dc50`: strings recuperadas no run 36781489336 identificam
  explicitamente **DPETorchModelV2 / DPETorchModelV1**. Não significa CPU versus
  DSP, nem fallback funcional em MediaTek. Próximo alvo: auxiliar V1
  `FUN_01718660` e executor V2 `FUN_0172bee0`.
- XNNPACK/ATen/boltnn presentes não provam uso pelo caminho de mãos nem que possam
  substituir o backend original no telefone.

## 4. Busca ampliada em andamento

`.github/workflows/hand-optimizations.yml` reconstrói ODM verificado, verifica o
hash do engine e faz uma importação Ghidra com três passagens independentes:

1. Inferência: quantização, batching, delegação e representações de tensor.
2. Memória: pooling, preallocação, reuse, alinhamento, candidatos a zero-copy.
3. Temporal/agendamento: predição, filtros, ROI, downsampling, threads e scheduler.

Até 64 strings por grupo e 24 funções por passagem, com endereços, contagens de
truncamento, C-like, prefixos de disassembly e callees. Strings com contexto de
mãos têm prioridade; strings genéricas são rotuladas e **não** viram automaticamente
“otimizações de hand tracking”. Análise automática limitada a 900 segundos.
Não é varredura exaustiva nem inclui todas as bibliotecas/DSP/firmware vendor.

Ainda falta provar ativação por call chain, condições e frequência por frame,
recuperar implementações fora do engine, validar ABI, portar dependências de
hardware e medir qualidade/latência no telefone. Relatórios novos são publicados
pelo workflow; não alteram retroativamente estes níveis de comprovação.

## 5. Resultado da primeira busca ampliada e continuação

Run **36784585864** concluiu: 72 seleções / **71 funções distintas**, todas com
C-like recuperado, não ABI validada. O scan achou 1771 strings candidatas de
inferência, 26 de memória e 615 temporais; os grupos 1 e 3 foram truncados para a
seleção inicial. Esses números são candidatos, não número de otimizações.

A continuação preserva **todos os candidatos que o scanner reconhece** (limite
explícito de 8192/grupo), inclusive além da primeira página. O novo script
`TraceHandOptimizations.java` registra referências diretas desses candidatos e
callers dos alvos abaixo, antes de escolher funções para decompilar. Não resolve
automaticamente despacho virtual; ausência de referência não prova código morto.

### Novas observações concretas, sem confundir infraestrutura com otimização

- `FUN_0193ffd0`: valida índice de scheduling de HandPrototypeTracking (0–7;
  fora disso usa 4) e chama callback. **Não são valores de prioridade Linux**;
  não se deve passar 4 para `setpriority` ou requisitar scheduler privilegiado.
- `FUN_00b2e090`: configuração de downsampler de taxa com flags, duração/período,
  conversão por `1e9` e ramo que combina taxa com duração/período. Ainda não é o
  algoritmo por frame, nem foi demonstrado que todo caminho de mãos o ativa.
- `FUN_00b69590`, encontrado por “hand pose filters”, serializa configuração.
  **Não recuperamos um filtro temporal executável só por achar essa string.**
- `FUN_01953880`, encontrado por `CNNVizardHandBboxDetector`, é formatação/log de
  parâmetros, não o detector em si. A próxima passagem prioriza seus callers.
- `FUN_01718660`: carregamento V1 com helpers `0171c420`, `0171c680`, `0171c820`;
  selecionados para aprofundar metadados/conversões, sem chamá-los de fallback CPU.

### Layout de memória planejada: 16 e 128 bytes

Em `FUN_00e1ec40` (VA ELF `0xd1ec40` do engine verificado), o C-like mostra:

- acumulador arredondado por `(total + tamanho + 0xf) & ~0xf`;
- outro ramo, condicionado pelo tipo observado, arredondando por
  `(total + tamanho + 0x7f) & ~0x7f`;
- alocação do primeiro bloco com argumento de alinhamento `0x10`;
- alocação indireta do outro bloco com argumentos `0x19, 1, tamanho`;
- reservas de vetores condicionadas à capacidade disponível.

**Não é prova de zero-copy ou de zero alocação por frame.** Esse caminho também
libera/recria arenas; ainda falta confirmar frequência e lifetime pelos callers.
A associação ao componente Hexagon vem de referências recuperadas, não valida
uma assinatura da chamada indireta nem um allocator compatível com MediaTek.

`hand_arena_layout.{hpp,cpp}` isola as duas regras de alinhamento sem alocar,
sem inventar layout privado e sem substituir o allocator original. Rejeição de
overflow e contador desalinhado é proteção própria do MetaPort, separada da regra
original observada. Testes ASan/UBSan: 2002 blocos acumulados, fronteiras e falhas
sem modificar saída. Ainda não conectado ao executor; não implica ganho medido.

### Estado da implementação anterior

Build Android **36784585834** passou (`gradle_exit_code=0`) com a regra SIMD de
material incorporada. Compilação ARM64 não substitui teste físico da função nem
integração do renderer. Continua ausente a bridge privada de poses/materiais.

### Dependências fora do engine

Novo workflow `hand-dependencies.yml` inspeciona, em ODM/vendor verificados,
configuração e init do serviço, tracking host/vendorutils, bibliotecas RPC/Hexagon
e `libQnnBoltnnOpPackageV69.so`. Registra máquina ELF, dependências dinâmicas e
excertos de configuração relevantes. Não executa código, não altera prioridades
no aparelho e não supõe que um backend DSP seja carregável no processo ARM64.
A whitelist não é o fechamento transitivo completo de todas as dependências.

## 6. Call chains e backend DSP: resultados da continuação

**Run 36787226058 concluído:** cobertura de referências de **2370 strings únicas**
que casam com o scanner, não de todas as strings/código do firmware. Recuperou:

- `019513a0 → 01953880`: agora há o construtor que consulta parâmetros e fornece
  batch/stack ao logger do detector de mãos. Dois campos têm fallback 1; isso não
  prova que os modelos em uso tenham batch 1, nem recupera o algoritmo do detector.
- `0173c830 → 00e1ec40`: construção/carregamento chama o planejamento de arenas.
  Não se declarou que o planejamento ocorre a cada frame ou nunca ocorre depois.
- `01c214a0`, `00b2e220`, `01c00890 → 00b2e090`: callers do configurador de taxa;
  permanece pendente separar as rotas compartilhadas de câmera das rotas de mãos.
- `00b694d0 → 00b69590`: reforça o caminho de configuração, não algoritmo de filtro.

Os nomes `DPEPredictorV2` e `getHandTrackingThreadPriorityCallback` não apresentaram
referências diretas de código nesta passagem. A próxima percorre uma hipótese
limitada de RTTI/pointers e registra os elos e candidatos. **Não define uma vtable
privada nem converte esses ponteiros automaticamente em chamadas executáveis.**

### Configuração e privilégios originais

Nos arquivos verificados do serviço aparecem `task_profiles trackingPolicy`,
`capabilities SYS_NICE`, usuário `system` e `ioprio rt 4`. O serviço APEX também
possui `disabled`. Isso é configuração embarcada, não prova de ativação no boot.
`wake_affine_controller = true` se refere a controller tracking no comentário;
`use_obj_track_cpuset = true` também não comprova otimização exclusiva de mãos.
Não copiar esses privilégios/CPU sets para um APK comum, nem tratar o índice de
SchedulingConfig como prioridade Linux. A adaptação precisa respeitar as APIs e
permissões efetivas do telefone, sem root/desbloqueio.

### Hexagon: finalmente instruções, não só dependências

Run **36789064019** publicou novo `hand-dependencies-report.json`:

- `libhexagon.so` ARM64 depende de `libcdsprpc.so`; RPC depende, entre outras,
  de `vendor.qti.hardware.dsp@1.0.so`, `libdmabufheap.so` e `libvmmem.so`.
- `libhexagon_skel.so` e `libQnnBoltnnOpPackageV69.so` são ELF32, máquina 164,
  flags `0x69` (V69). Não são bibliotecas ARM64 executáveis diretamente no APK.
- O primeiro objdump devolveu **zero instruções com exit 0**. Não foi tratado como
  recuperação bem-sucedida. Uma view ELF de análise reconstrói seções sobre cópias
  byte-exatas dos PT_LOAD executáveis, mantendo seus VAs. Não é firmware para
  carregar/flashear; o original permanece intocado e os hashes são registrados.
- Com perfil explícito `hexagonv69,+hvxv69,+hvx-length128b`, aparecem **32038 e
  3475 linhas com sintaxe de registradores vetoriais**, respectivamente. Exemplos:
  `vsplat`, `vmem`, `vmemu`, `vxor` e `vadd` com operandos `.sf`/resultado `.qf32`.
  Isso revela vetorização nas dependências do backend; **não prova quais kernels
  cada modelo de mãos executa**, nem que largura 128 B esteja ativa em runtime.
- Ainda há **50552 e 25839 linhas unknown/invalid** nesse perfil. Os segmentos
  executáveis podem incluir dados; contagens de linhas não são número de funções,
  otimizações, instruções válidas ou porcentagem de port concluído.
- Não substituir `.qf32` por float ARM/NEON por adivinhação: precisam de validação
  numérica e das regras originais de arredondamento/representação.

A identificação V69 e os nomes do perfil usam a referência pública LLVM 14.0.6:
`llvm/include/llvm/BinaryFormat/ELF.h` e `llvm/lib/Target/Hexagon/Hexagon.td`, tag
`llvmorg-14.0.6` do repositório `llvm/llvm-project`. Nenhuma execução DSP ocorreu.

### Publicação e validação

Runs 36787460895 e 36788324026 falharam na etapa de publicação, não na etapa de
inspeção. Seus resultados não foram reclassificados como sucesso. O publisher
passou a atualizar o checkout limpo antes de copiar relatórios e tratar corridas
de push. O run 36789064019 publicou com sucesso a view corrigida, preservando
inclusive segmentos que incluem o cabeçalho ELF.

Build Android **36787628516** passou com a aritmética de arenas incorporada.
Ainda sem validação física, alocador original no MediaTek ou execução dos modelos.

## 7. Operandos DSP e primeira redução inteira adaptada para ARM64

Run **36791887928**, confirmado novamente em **36792806075**:
`hvx_decoder_probe.hvx_operand_evidence` preserva tipos, sinais, imediatos e
forma de par de registradores. Normalizar nomes de registradores NÃO preserva
alias/dependências; janelas +/-8 linhas não delimitam kernels ou pacotes completos.

No skeleton, `.uw = vrmpy(.ub,.ub)` aparece em `0x637bc` (29 ocorrências textuais)
e `.uw += vrmpy(.ub,.ub)` em `0x66e40` (424). No pacote QNN, a primeira forma
aparece em `0x4dac0` (2). São endereços da view ELF byte-exata; caminho ativo dos
modelos de mãos continua não validado. Formas signed e scalar-register são tratadas separadamente na ampliação abaixo;
saturadas, lookup e QFloat continuam fora desta implementação.

**`hand_u8_reduce.{hpp,cpp}`** inicialmente adaptou a redução unsigned vetor-vetor:
cada grupo de quatro bytes produz um acumulador de 32 bits, com atribuição ou
soma módulo 2^32. Baseline ARM64 NEON faz multiplicação alargada, somas de pares
alargadas e soma final de pares; não exige a extensão opcional dotprod. Os 128
bytes da API são uma escolha explícita deste helper, não medição do HVX ativo.
Não há heap, quantização, execução de tensor, substituição de kernel, bridge
HexagonRpcBackend nem ganho de desempenho medido.

Referência pública de semântica: QEMU v9.0.0,
[`target/hexagon/imported/mmvec/ext.idef`](https://github.com/qemu/qemu/blob/v9.0.0/target/hexagon/imported/mmvec/ext.idef),
`vrmpyubv` / `vrmpyubv_acc`, linhas 732–744; SHA-256
`96162f9008587e2f97f1893c0632da7f9a0780e6a1dc2219cc905dac22c51717`.
Esse arquivo de referência é Copyright Qualcomm Innovation Center 2019–2023,
GPL-2.0-or-later, e não foi incorporado ao repositório. A implementação MetaPort
é código próprio GPL-3.0-only; isso não relicencia os binários originais.

Teste local host passou com ASan/UBSan: todos os 65536 pares de bytes, posições
variadas, 4096 vetores determinísticos e overflow, comparados com fórmula
independente em uint64. A CI agora também compila e executa **o nosso backend
ARM64 NEON** sob qemu-aarch64. A inclusão da etapa não significa que já passou;
a primeira execução, **36793722930**, passou no host, ARM64 emulado, build AAR,
testes Java e lint Android. Não é execução do DSP original
nem teste físico no X6873.


### Ampliação para as oito formas `vrmpy` observadas

O helper agora também contém vetor unsigned × vetor signed e as duas variantes
com quatro coeficientes de registrador escalar, cada uma com atribuição ou
acumulação. Isso corresponde às **8 formas textuais vrmpy observadas** (5838
ocorrências somadas no skeleton), não à ISA inteira, a 5838 otimizações ou a um
kernel completo. Os coeficientes escalares são fornecidos em bytes, menos
significativo primeiro, e expandidos em stack antes da redução; desempenho não
medido. O resultado signed é mantido como bits uint32, evitando overflow signed
indefinido em C++.

Referência adicional no mesmo arquivo QEMU: `vrmpyub`/`vrmpyub_acc` (717–729),
`vrmpybus`/`vrmpybus_acc` (794–807) e `vrmpybusv`/`vrmpybusv_acc` (838–851).
A variante mixed NEON alarga os operandos, multiplica em int16 (produtos cabem),
alarga as somas de pares para int32 e acumula os bits módulo 2^32.
Testes host ASan/UBSan passaram também para todos os 65536 pares unsigned/signed,
vetores variados, coeficientes ordenados e cruzamentos das fronteiras signed.
**Run 36794546518 passou**: host sanitizado, as quatro APIs no backend ARM64
NEON sob qemu-aarch64, build AAR, testes Java e lint Android. Isso valida as
reduções contra a fórmula de referência, não o DSP ou o telefone. Nenhum desses
helpers está ligado ao caminho de inferência original.

## 8. Scheduler, compartilhamento de câmeras e FMQ do serviço original

`/odm/bin/trackingservice`, SHA-256
`a6474bc3710558a26827a5165556a99cd998b013233072eefe4edf2b6b2f1945`.
Runs **36791709535**, **36792751892**, **36793839057**; os endereços abaixo são
Ghidra (base `0x100000`), não endereços utilizáveis num APK. Relatórios atuais
substituem a seleção anterior; o histórico Git preserva as extrações anteriores.
São caminhos de um serviço compartilhado, **não todos exclusivos de mãos**.

### Políticas e prioridade da movimentação de buffers

A configuração original `thread_priority.cfg` foi recuperada em **36792806075**:

| Seção | Política / valor declarado |
|---|---|
| syncbossWorkerPriority | Realtime / 52 |
| headsetPosePriority / controllerPosePriority | Realtime / 51 e 50 |
| cameraWorkerPriority | Realtime / 48 |
| controllerWorkerPriority | Normal / 110 |
| motionStreamerPriority / controllerStreamerPriority | Normal / 101 |
| cameraStreamerPriority | Normal / 100 |
| backgroundPriority / normalPriority | Normal / 139 e 120 |
| computePriority | Batch, valor ausente |
| elevatedPriority | Normal / 100, perfil SoftRealtimePerformance |
| isochronousPriority | Realtime / 1, affinity `110000` |
| latencyCriticalPriority / graphicsCriticalPriority | Realtime / 48 e 49 |

Os comentários originais justificam prioridade do consumidor Syncboss para
esvaziar a FIFO antes de perder mensagens, e das threads de câmera que movimentam
buffers/dados acima dos consumidores. Isso documenta intenção de engenharia;
não mede perdas, deadlines ou ativação das políticas. Não chamar todos esses
workers de threads exclusivas de mãos.

`005de4c0` valida Realtime entre 1 e 99, Normal entre 100 e 140, e Batch com 0
(default quando ausente). O comentário da configuração relaciona Normal a nice;
a conversão/aplicação efetiva no kernel ainda não foi recuperada. `005df5c0`
consulta uma tabela e usa 1 como fallback; não é a syscall de scheduler.

**Detalhe que não pode ser adivinhado:** `005df6c8` zera 128 bytes de máscara e
mapeia o caractere **de índice i para o bit i**, se diferente de `'0'`, limitado
a 1024 bits. Portanto `110000` produz bits **0 e 1**, não 4 e 5. Não trasladar
esses IDs de CPU para o MediaTek nem inferir quais são cores rápidos.

Os perfis vendor recuperados em **36794054709** definem:
- `trackingPolicy`: cpuset `tracking`, grupo cpu `xr`, extensão `HzosExt/ALLOW_RT`;
- `objectTrackingPolicy`: cpuset `object_tracking`, `HzosExt/ALLOW_RT`;
- `SoftRealtimePerformance`: grupo cpu **`soft-rt`**, sem uclamp declarado nessa
  definição. Ele foi encontrado seguindo a referência da configuração, não
  porque seu nome contém hand/tracking. Ausente no arquivo system inspecionado.

A extensão Hzos e grupos privilegiados não são concedidos a um APK comum.
Não foram aplicados no telefone, emulados como se fossem garantias reais, nem
substituídos por números nice escolhidos ao acaso.

### Alteração de política, atividade agregada e supressão de transições

- `0035a27c` percorre objetos de câmera com stride `0x108`, solicita alteração
  da string de perfil e registra “Moved hand tracking camera threads”.
  **O helper `00319b10` apenas grava a string e marca `+0x100 = 1`**. Não contém
  uma syscall que prove aplicação imediata. O caminho é de configuração
  DevChoice, não comprovação da configuração padrão.
- `00359d90` manipula o modo mux de mãos e encaminha a atualização de estado.
  `0031b044` percorre sistemas registrados e chama `0031a3e4`.
- `0031a3e4` calcula atividade agregada de consumidores de um stream, atualiza
  a entrada do sistema atual e compara atividade anterior/nova. Quando a
  mudança está habilitada, só chama os slots de início/parada (`+0x28/+0x30`)
  na transição efetiva. Há override de atividade e tratamento distinto do
  estado 3. Isso recupera lógica de compartilhamento e evita transições
  redundantes nesse caminho; enums/objetos e integração Camera2 não validados.
- `0037cc2c` protege uma atualização temporal; `00381b88` suprime estados iguais
  em timestamps normalmente não decrescentes, com contador previamente não
  nulo. Regressões temporais e NaN exigem preservar a comparação original,
  não tratar isso como filtro de confiança de mão.

### FMQ: tamanho agora rastreado, não “zero-copy” presumido

Cadeia `005a2e9c → 005a4574 → 005a4634`: solicitação `0x10`, flag 1, FD -1.
O inicializador rejeita tamanho zero/excessivo e calcula **capacidade × `0x210`**,
usa `ashmem_create_region("MessageQueue", ...)`, proteção 3 e descriptor/mapeador.
Para esse ramo, são **16 unidades de 528 bytes**, 8448 bytes de área de dados;
soma `0x14` e arredonda com máscara de 4096, produzindo **12288 bytes** de região
solicitada. Layout interno dos 528 bytes e protocolo de leitura/escrita ainda
não estabelecidos. Isso não prova ausência de memcpy ou Binder em outros pontos.
O arredondamento original de 4 KiB não deve ser copiado cegamente para páginas
Android de outro tamanho. Não existe ainda bridge FMQ original no APK.

## 9. Ponteiros recuperados e entrada de processamento DPE V2

Run **36791437773** concluiu com sucesso. O scanner de ELF e o Ghidra recuperaram
funções em slots associados por hipótese RTTI a `DPEPredictorV2` e ao callback
de prioridade. A primeira seleção incluiu destructors/clones; foi ampliada para
até 8 alvos únicos/tipo, com índice de slot e separação inferência/scheduler.
Não é validação do layout completo da vtable ou de uma chamada em execução.

- `01717140`, ligado ao DPE V2 pelos ponteiros: inicializa resultado de `0x560`
  bytes, prepara dois grupos de entradas, chama **`01716f20`**, mede tempo e
  processa scores. Há sentinela `FLT_MAX → -1`, fórmulas
  `1 / (expf((valor-limiar)*300) + 1)` e um ramo agregado alternativo com
  constantes 1.1 e -45. Os tipos reconstruídos de alguns valores packed são
  ambíguos; não foram convertidos diretamente em código de produção.
- A mesma função contém alocação/liberação e dispatch virtual condicionado;
  não suporta uma alegação geral de “sem alocação por frame” ou de seleção
  CPU/DSP. Significado dos campos, dos dois grupos e dos scores não validado.
- O slot 6 do callback aponta para **`0193ffd0`**, já analisado como normalização
  de enum e encaminhamento de callback, não como aplicação de prioridade Linux.
- A continuação **36793839065** seleciona também o callee `01716f20`, o construtor
  V2 `017222a0` e listings de até 1024 instruções para conferir a aritmética.
  Resultado dessa continuação ainda pendente.

**Continuam NOT PORTED YET:** ABI/call-chain completa dos modelos, runtime DSP
no MediaTek, produtor/consumidor FMQ, políticas efetivas do serviço, câmera e
inferência integradas, renderer original completo e validação física. Nenhuma
porcentagem ou declaração de “todas as otimizações encontradas” foi emitida.


### Continuação da seleção

O scanner de ROI foi refinado para reconhecer `roiHeight`, `roi_width`,
`QuantizedRoiAlign`, `RoIAlignForwardCPUKernel` e plurais, sem aceitar substrings
incidentais em Android, centroid ou Meroitic. O teste cobre as grafias observadas
na listagem anterior. Isso corrige tanto falsos positivos quanto a perda de
identificadores causada pela correção anterior baseada só em `\broi\b`.
A alteração será usada na próxima varredura; não muda retroativamente os reports.

`TraceHandService.java` passa a rastrear callers diretos de funções de scheduler,
afinidade e task profiles, incluindo thunks, no binário de serviço pinado. Limites:
128 refs/raiz, 2 callers novos/raiz e 24 funções no total. Chamadas indiretas e
números de syscall bruta continuam não resolvidos. A continuação **36794645662**
também inspeciona os helpers FMQ `005a4bb4` e `005a4f04`; resultado pendente.


## 10. Aplicação real das políticas recuperada; continuação DPE/FMQ

**36794645662 e 36793839065 concluíram com sucesso.** Isso supera os estados
pendentes registrados nas seções anteriores, não valida execução no telefone.

### Scheduler: agora há syscall e ordem de aplicação

O trace recuperou **`005df1ac` (`setPriorityReturnErr` no log original)**:
1. conta bits da máscara de 128 bytes; se vazia, não chama `sched_setaffinity`;
2. se houver perfis, chama `SetTaskProfiles(tid, perfis, false)`;
3. monta atributos e chama **`syscall(0x112, tid, &attr, 0)`**. Em AArch64 Linux,
   274 é `sched_setattr`; a chamada e argumentos são visíveis no listing;
4. erro de afinidade ou perfil interrompe esse caminho antes da syscall final.

O ramo Normal faz `sub w8,w8,#0x78` e grava só 32 bits em `sp+0x10`, após zerar
os campos: **nice = valor - 120**, prioridade RT permanece zero. A aritmética foi
conferida no assembly, não apenas no C-like que apresenta casts ambíguos.
Batch grava política 3; ambos gravam flags 1. O ramo Realtime carrega um literal
de 16 bytes em `00172840` e grava o valor no campo de prioridade. Esse literal
será capturado antes de afirmar FIFO versus RR ou flags específicas desse ramo.
A confirmação de uma chamada estática não prova sucesso da syscall nem a ligação
com cada worker de mãos. Um APK comum não recebe automaticamente os grupos e
privilégios do serviço Horizon.

`005df4e0` aplica somente perfis e retorna erro quando `SetTaskProfiles` falha.
A próxima seleção segue callers desses dois helpers e do construtor
`005a2ce8`, para aproximar os mecanismos compartilhados dos usuários concretos.

### FMQ: descriptor e leitores

`005a4bb4` monta grantors de 8, 8, área de dados e, opcionalmente, 4 bytes, com
alinhamento de 8; grava quantum 528 e flavor **2**. `005a4f04` confere o quantum,
aloca contador local de leitura de 8 bytes, mapeia contador de escrita, dados e
flag de evento, e chama `EventFlag::createEventFlag`.

Isso corresponde à estrutura do FMQ **unsynchronized-write**, com posição de
leitura independente. Referência pública de enum: LineageOS Android 14,
[`base/fmq/MQDescriptorBase.h`](https://github.com/LineageOS/android_system_libfmq/blob/lineage-21.0/base/fmq/MQDescriptorBase.h),
blob `7303917623ac37915fdd33f195010db481f39f0b`, SHA-256
`69d61adc1c0123ce90f9abc6956a7305126b3ee7e970c08d8569b718f7ffaa0b`:
`kUnsynchronizedWrite = 0x02`. Essa referência Apache-2.0 não é código Meta.
A [documentação AOSP de FMQ](https://source.android.com/docs/core/architecture/hidl/fmq)
descreve um escritor e múltiplos leitores, com possibilidade de perder dados
quando um leitor não acompanha. **Ainda falta recuperar o produtor e seus
métodos de escrita**, portanto não afirmar ausência de bloqueio/cópia em todo o
caminho de mãos. O próximo helper é o mapper `005a5134`.

### DPE: cópia e escala SIMD antes do próximo estágio

`01716f20` foi recuperado: aloca/copia registros de **64 bytes**, multiplica
três floats nos offsets **0x30, 0x34 e 0x38 por 0.001**, encaminha para
**`01724fc0`** e libera a cópia. O listing confirma `fmul v2.2S` e `fmul s3`
com stride `0x40`, em vez de conversão inteira sugerida por casts no C-like.
É compatível com escala de componentes de transformação, mas não identifica
sozinho o tipo privado, coordenadas ou unidades de entrada. Não aplicar uma
conversão de pose ARCore por palpite. A próxima seleção segue `01724fc0`.

A suíte Python atual tem **88 testes, 1 skip**; o backend ARM64 das oito formas
vrmpy observadas e o build Android passaram em **36794546518**. Ainda não há
inferência de mãos completa, ganho medido no X6873 ou ZIP/Release final.

## 11. Packing saturado observado: três aritméticas adaptadas

`hand_saturating_pack.{hpp,cpp}` implementa os resultados numéricos de três formas
observadas em `hand-dependencies-report.json`, em vetores de 128 bytes:

| Forma | Exemplo skeleton / QNN (VA da view) | ARM64 |
|---|---|---|
| `.h = vpack(.w,.w):sat` | `61e70` / `39fb4` | `vqmovn_s32` |
| `.uh = vpack(.w,.w):sat` | `119608` / `39bac` | `vqmovun_s32` |
| `.ub = vpack(.h,.h):sat` | `61e84` / `39fc0` | `vqmovun_s16` |

A ordem é importante: **Vv, o segundo argumento, preenche a metade baixa; Vu,
o primeiro, a alta**. Não há interleaving de elementos. Essa ordem e os tipos
são conferidos na referência QEMU v9.0.0 `mmvec/ext.idef`, linhas 419–439,
mesmo SHA-256 `96162f9008587e2f97f1893c0632da7f9a0780e6a1dc2219cc905dac22c51717`
citado anteriormente. Não foi implementada a variante de saída signed-byte,
que não apareceu nas formas capturadas neste levantamento.

Teste local ASan/UBSan passou: todos os 65536 valores int16, limites int32,
valores ao redor dos thresholds de saturação, ordem de lanes/fontes, fontes
iguais e 4096 pares de vetores determinísticos. CI foi ampliada para executar
as mesmas verificações no backend ARM64 emulado e compilar a biblioteca Android;
**essa nova execução ainda está pendente**.

É aritmética isolada, não integração com quantização dos modelos ou emulação
completa de instruções: flags DSP, predicados, pacotes, endianness da memória e
ativação do kernel permanecem fora do contrato. As instruções saturadas NEON
podem marcar FPSR.QC no ARM; isso não emula status do Hexagon. Não há ganho de
FPS medido nem justificativa para converter QFloat em float comum.
