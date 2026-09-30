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
