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
