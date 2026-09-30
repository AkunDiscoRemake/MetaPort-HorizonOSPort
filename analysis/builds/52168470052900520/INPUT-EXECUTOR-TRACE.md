# Rastreamento do executor original de entrada

**Conversão de câmera, inferência e bridge de mãos: NOT PORTED YET.**
Este documento registra análise estática, não código original recuperado com tipos
corretos, ABI chamável ou funções testadas contra a câmera.

## Execuções

1. [36760566655](https://github.com/AkunDiscoRemake/MetaPort-HorizonOSPort/actions/runs/36760566655),
   source `f50be5e`: seleção inicial de 21 funções por construtores/strings.
   As janelas de ponteiros não tinham DataReferences produzidas pelo Ghidra;
   portanto esse resultado **não havia recuperado os métodos dessas janelas**.
2. [36763266289](https://github.com/AkunDiscoRemake/MetaPort-HorizonOSPort/actions/runs/36763266289),
   source `e55c3e5`, relatório automático `255317c`: passagem focada, com 180 s de
   orçamento de análise automática e até 32 funções selecionadas. Foram produzidas
   reconstruções C-like de **11 funções candidatas**, nove selecionadas pelos
   ponteiros e duas pelos construtores já observados.

O relatório atual é `hand-input-decompilation.json`, ligado a
`hand-input-run.json`. A passagem focada não substitui a análise geral da engine
nem indica decompilação completa. Relatórios anteriores permanecem no histórico Git.

## Identidade e seleção

As rotinas `prepare_input.py` e `DecompileHandInput.java` exigem a engine de SHA-256
`10eac37188c97389dabfe7599a354d146d1e6223d849546d230796af93418ffe`.
A imagem ODM também é conferida contra a reconstrução verificada da OTA fixa.
Não se aplicam esses endereços a outras versões.

O construtor observado em Ghidra `FUN_01720ce0` atribui os address points
ELF `0x268b708` e `0x268b758`. Foram lidos 12 slots de cada janela, como **candidatos**:
essas janelas se sobrepõem parcialmente e atravessam limites possíveis de tabelas.
Elas contêm também dados e ponteiros não executáveis, não apenas métodos.

Quando faltam DataReferences, a ferramenta agora lê o valor na memória **já
relocada do Ghidra**, sem somar o image base novamente. Apenas endereços alinhados
em blocos executáveis são considerados para disassembly/criação de função.
Não há chamada do ponteiro, `dlopen` da engine ou execução de firmware.

## Candidatos observados

Para o address point ELF `0x268b758`, no projeto Ghidra com image base `0x100000`:

| Offset da janela | Função no projeto Ghidra | Observação estática, não assinatura ABI |
|---:|---|---|
| 0 | `FUN_0172bb60` | libera estruturas internas e chama destruição do objeto mantido |
| 8 | `FUN_0172bc80` | caminho semelhante, seguido de liberação do próprio objeto |
| 16 | `FUN_00cd6dd0` | retorno constante zero |
| 24 | `FUN_0172bd80` | consulta ao método `forward`, codificado também em constantes imediatas |
| 32 | `FUN_0172bee0` | adaptação de descritores de tensores, despacho e conversão de descritores de saída |

Também foram observados wrappers de liberação/despacho na primeira janela.
A alocação e os dois address points são compatíveis com armazenamento de objeto
mais controle de ownership, mas **não se declara um layout de `shared_ptr` privado
nem se permite reinterpretar um objeto do NDK como esse objeto original**.

O candidato `FUN_0172bee0` referencia `FUN_017556c0` no caminho de despacho e lê
metadados dos tensores. Isso **não recupera a fórmula de quantização**, a escala
de luminância, o crop ou a conversão entre o frontend `v2` e o tensor Byte do PTE.
Não foi escrito um conversor Camera2 presumindo que copiar bytes ou aplicar uma
escala isolada preserve o comportamento original.

## Qualidade e limites

- O Ghidra ainda emite advertências de propagação de tipos e chamadas indiretas.
- Reconstruções podem misturar caminhos de erro, landing pads e código adjacente
  quando helpers não-retornantes não são reconhecidos. Limites/assinaturas e
  convenções de retorno precisam de confirmação por instruções/unwind/runtime.
- `DECOMPILED_NOT_VALIDATED` significa apenas que o decompiler produziu C-like.
- Descobrir um método que retorna zero não autoriza criar um stub de sucesso.
- A consulta `forward` e os candidatos de despacho não provam que o backend
  HexagonRpcBackend seja executável no Infinix.

A próxima dependência técnica é seguir a preparação dos tensores antes desse
despacho e recuperar seus contratos de ownership/tipo/quantização, sem apagar a
diferença já medida entre `use_uint8_input=false` e a entrada compilada Byte.
