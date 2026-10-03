# Modelos compactados de mãos — continuação do port

**Continuação posterior:** [atributos originais e comparação C++ independente](ATTRIBUTES-REFERENCE-VALIDATION.md).
Os blobs MessagePack DPE31/32 foram recuperados. Os 13 avisos do leitor estrito
agora possuem leitura Int64 independente e reprodução pública de vtable
compartilhada; as advertências não foram apagadas nem os campos reduzidos a 32 bits.
O texto abaixo preserva os resultados da etapa anterior.

## O que foi implementado

- `handtracking/ai/ptez.py`: exploração limitada do container `etz0`, descompressão
  deflate com limite de saída, verificação de comprimento/fim do stream e estrutura
  inicial FlatBuffer. Não carrega modelos nem executa operadores.
- `handtracking/ai/pte_schema.py`: leitor limitado de tabelas, vetores, strings,
  tipos/formatos de tensores, constantes escalares e referências de instruções.
  Há limites por campo e orçamento global contra vetores compartilhados que poderiam
  multiplicar o trabalho/saída de um parser ingênuo.
- Workflow separado `hand-models.yml`: usa a mesma OTA com hash fixado, reconstrói e
  verifica ODM, publica somente relatórios. Modelos originais e descompactados ficam
  no runner, não são enviados a Git nem aos artifacts.

Referência estrutural: [ExecuTorch v0.7.0, schema/program.fbs](https://github.com/pytorch/executorch/blob/v0.7.0/schema/program.fbs),
blob Git `7308cc631994146e037b7a88749aa4c8e87fe93a`. Essa referência pública **não foi
estabelecida como a versão exata do schema privado da firmware**. Resultados são
rotulados `PUBLIC_SCHEMA_CANDIDATE_NOT_RUNTIME_VALIDATED`, não conformidade completa.

## Resultado observado nos originais

Dez arquivos `.ptez` antes opacos foram descompactados:

- DPEV31MG e DPEV32MG;
- SKBV30, SKBV31 e SKBV32;
- STPV30, STPV31, STPV31_Day0, STPV32 e STPV32_Day0.

Todos os dez apresentaram header `etz0`, tamanho declarado de header 24, método
`deflate`, padding até o offset **64** e stream zlib (`wbits=15`). O tamanho de saída
coincidiu com o declarado, o stream foi consumido integralmente, e a saída apresentou
identificador **ET12** e estrutura inicial consistente. Isso é descompressão, **não
quebra de criptografia**, autenticação de procedência ou prova de funcionamento.

O primeiro ensaio foi **36730744296**, fonte `c14d4a4`; a leitura inicial de planos
foi medida em **36731324236**, fonte `1cd78c1`; referências de instrução foram
verificadas em **36731722740**, fonte `204218f`. Consulte `model-analysis-run.json`
para a revisão e execução mais recentes e `ptez-report.json` para os hashes completos.

## DPE31/DPE32: formatos recuperados

Em ambos, o plano `forward` contém **12 entradas e 10 saídas**. Exemplos de entradas:

| Slot de entrada | Código escalar serializado | Formato |
|---:|---:|---|
| 0 | 0 | `[4, 1, 96, 96]` |
| 1 e 2 | 6 | `[4, 4, 4]` |
| 3 | 6 | `[2, 1, 1, 1]` |
| 4 e 5 | 6 | `[2, 4, 4]` |
| 6 | 6 | `[2, 18, 4, 4]` |
| 7 e 8 | 6 | `[2, 22, 3]` |
| 9 | 6 | `[2, 21, 3]` |
| 10 | 11 | `[2]` |
| 11 | 6 | `[4, 63, 1, 1]` |

Esses são metadados de tensores, não a ABI de poses. **O número 4 não demonstra
quatro câmeras**, e nomes como calibração, estado temporal ou posição não foram
atribuídos aos slots por suposição. Não duplicar uma imagem do telefone para preencher
uma dimensão e declarar tracking válido. A interpretação depende do preprocessamento
original e dos callbacks/consumidores do engine.

As saídas incluem `[2,20]`, `[2,21]`, `[2,18,4,4]`, `[4,21,24,24]` e outras formas;
não correspondem automaticamente a um array de articulações OpenXR.

Foram encontrados planos adicionais `get_attributes_msgpack`, `input0_scale`,
`input0_zp`, `input0_quant_min`, `input0_quant_max` e `input0_dtype`. O parser lê
constantes escalares serializadas sem invocar esses métodos. Em DPE31/DPE32, os valores serializados recuperados são `input0_scale =
0.003919653594493866`, zero-point `0`, limites `0..255` e código de dtype `0`.
Eles não substituem a recuperação do preprocessamento original.

Três modelos da geração 32 apresentaram campos escalares cujo tamanho não cabe
na interpretação pública de 64 bits. O leitor não os reduz silenciosamente para
32 bits: registra `SCALAR_LAYOUT_UNRESOLVED`, sem valor inventado, preservando os
outros metadados. A causa dessa discrepância ainda não foi determinada.

O payload MessagePack
retornado pelo primeiro deles ainda não foi extraído dos segmentos constantes.

## Dependência do backend: evidência mais forte que strings

O leitor distingue nomes presentes no arquivo de referências de instruções a
backends. Nos planos `forward` analisados:

| Família | Instruções enumeradas | Referências DelegateCall |
|---|---:|---|
| DPE31 e DPE32 | 43 | 2 para `HexagonRpcBackend`, com 4 e 17 índices de argumentos |
| SKB30/31/32 | 12 | 1 para `HexagonRpcBackend`, com 33 índices |
| STP30/31/32 | 125 | 1 para `HexagonRpcBackend`, com 38 índices |
| STP31_Day0/STP32_Day0 | 141 | 1 para `HexagonRpcBackend`, com 38 índices |

Os índices de argumentos e de backends são conferidos contra as tabelas. **O fluxo
de controle não é avaliado**, e instruções de outros tipos não são executadas nem
apresentadas como validadas integralmente. A presença de DelegateCall também não
prova qual ramo seria tomado numa execução real.

Strings `QnnBackend` aparecem nos arquivos, mas não foram confundidas com um backend
alternativo registrado nos planos acima. Não foi encontrada, nesses planos `forward`,
uma alternativa CPU enumerada na tabela de delegates. Isso **não demonstra ausência
de fallback em todos os outros arquivos/runtime da firmware**.

## Consequência para o port

É necessário adaptar ou substituir de forma compatível o processamento delegado,
ou localizar uma variante original realmente executável no hardware do telefone.
Carregar o arquivo em um runtime genérico de IA não resolve essa dependência.
Também faltam o contrato semântico dos inputs, calibração, sincronização, gestão de
estado e a integração com o serviço original. Nenhum retorno falso de sucesso foi
implementado para contornar esses requisitos.

**Hand tracking original em execução: NOT PORTED YET.** Esta etapa não altera o
estado da UI, do APK, do boot, dos Joy-Cons ou da Store. Nenhum telefone foi modificado
ou servidor Meta contatado.

## Última verificação

Actions **36732556258**, fonte `c993e6e`: dez containers
descompactados; planos recuperados para os dez, com os escalares não resolvidos
explicitamente sinalizados. Validação local: 20 testes de tracking/parsers passaram;
53 testes existentes e 30 testes guest passaram com um skip opcional em cada suíte.
Nenhum desses testes é validação de inferência ou de uso no telefone.
