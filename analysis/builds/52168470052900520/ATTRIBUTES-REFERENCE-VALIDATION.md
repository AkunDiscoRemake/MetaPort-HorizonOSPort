# Atributos originais e comparação independente dos escalares

**Tracking original, bridge de câmera e APK completo: NOT PORTED YET.**
Nenhum modelo/delegate foi executado. Esta etapa recupera dados serializados e
confere a estrutura com um segundo leitor; não comprova inferência no Infinix.

## Atributos recuperados, sem chamar o getter

`handtracking/ai/pte_constants.py` lê o cabeçalho `eh00`, restringe referências
FlatBuffer ao `program_size` e localiza apenas um getter sem entradas, instruções
ou delegates, cujo único resultado seja um tensor Byte estático, imutável e
interno. Rejeita storage externo, alocação dinâmica, offsets fora dos segmentos,
storage ambíguo e blobs maiores que 16 KiB. O MessagePack é convertido para dados
JSON, sem hooks de extensões, chaves duplicadas ou números não finitos.

No run [36739796314](https://github.com/AkunDiscoRemake/MetaPort-HorizonOSPort/actions/runs/36739796314),
os dois `get_attributes_msgpack` foram recuperados do segmento constante 0,
índice 9, offset absoluto 49312, com 1366 bytes cada:

| Campo | DPEV31MG / DPEV32MG |
|---|---|
| `image_size` | `[96, 96]` |
| `use_uint8_input` | `false` |
| `input_format` | `"v2"` |
| `sigma_scales` | seis arrays de 22 números cada |

SHA-256 dos blobs MessagePack:

- DPE31: `fc20fbe8394b88325989cebfe40d3c038a3bcb7c08b4012e4733a29ea87cabf8`
- DPE32: `99007c3f93a5879e874e8a80e71c886b62cf3be37df68aba205ebb79d22af37d`

Os seis arrays têm nomes `MixedV_GT_SKEL`, `SingleV_GT_SKEL`, `MultiV_GT_SKEL`,
`MultiV_Use_PredS`, `MixedV_Use_PredS` e `SingleV_Use_PredS`. Seus valores diferem
entre os modelos e estão preservados em `ptez-report.json`; **não são uma
calibração medida da câmera do telefone**, nem uma tabela pronta de juntas OpenXR.
Os oito modelos SKB/STP não possuem esse getter de nome específico; a ausência é
registrada, não substituída pelos atributos dos DPE.

### Por que não copiar simplesmente bytes da Camera2

O plano compilado declara o primeiro tensor como Byte `[4,1,96,96]`, e seus
getters de quantização dão escala `0.003919653594493866` e zero point 0. Entretanto,
o atributo do frontend declara `use_uint8_input=false` e um formato privado `v2`.
São camadas de contrato distintas: os metadados **não demonstram** que o frontend
recebe o mesmo buffer quantizado do grafo, nem que `v2` signifique um formato de
pixel Android. Falta rastrear e preservar a conversão original entre essas camadas.

A função decompilada `FUN_017222a0` em `hand-decompilation.json` consulta
`image_size`, `use_uint8_input` e `input_format`. Isso liga os nomes recuperados
a um consumidor original; a função continua C-like não validado, não uma ABI
chamável. `FUN_016ef500` contém caminhos/logs distintos para detector single-view
e multi-view. Nem os nomes nem o tamanho de batch estabelecem quatro câmeras
físicas obrigatórias ou viabilidade monocular no telefone.

## A divergência de tamanho dos escalares

O leitor Python conservador continua mostrando 13 `SCALAR_LAYOUT_UNRESOLVED`:
cinco no SKB32 e quatro em cada STP32. Agora há evidência dos bytes: todos esses
casos referenciam uma vtable `060008000400`, que declara objeto de 8 bytes e campo
no offset 4. Um Int de 64 bits exige ler até o offset 12. O leitor conservador
recusa essa leitura, **sem converter o campo para 32 bits**.

Foi implementado `reference_probe.cpp`, compilado com headers produzidos por
`flatc` a partir do schema público ExecuTorch v0.7.0, commit
`4b9d44206a99c1ce39315487599971b257a02ed8`. Os dois arquivos de schema são
verificados por SHA-256 no workflow. O programa:

- não liga ExecuTorch nem carrega qualquer backend;
- verifica a região do programa com `VerifyProgramBuffer`;
- usa os accessors gerados para Int64, apenas em getters constantes selecionados;
- não chama os métodos originais;
- mantém seus resultados separados das advertências do leitor conservador.

No run [36740735279](https://github.com/AkunDiscoRemake/MetaPort-HorizonOSPort/actions/runs/36740735279),
o verificador público aceitou os **dez programas**. O compilador observado foi
`flatc version 1.12.0`; isso é uma versão da ferramenta de verificação, não a
versão comprovada do runtime privado do firmware.

| Modelos | num_layers | kernel_size | hidden_dim | left_context | featurizer_version |
|---|---:|---:|---:|---:|---:|
| SKB30 / SKB31 | 5 | 7 | 384 | 60 | 4 |
| SKB32 | 5 | 7 | 384 | 80 | 4 |
| STP30 / STP31 / STP31_Day0 / STP32 / STP32_Day0 | 6 | 16 | 128 | 31 | — |

Estes são valores de constantes serializadas lidos pelo accessor Int64 público,
não resultados de inferência. Não foram inferidas unidades para `left_context`.

### Reprodução independente da vtable compartilhada

Um teste sintético usa o **writer público Python FlatBuffers 25.2.10**, sem
firmware: primeiro serializa uma tabela Int32; em seguida uma tabela Int64.
O writer deduplica pela lista de offsets dos campos e pode reutilizar a vtable de
objeto de 8 bytes para a tabela de campo Int64. O teste reproduz exatamente o
prefixo `060008000400` e a advertência do nosso leitor estrito.

Isso demonstra um mecanismo público compatível com a discrepância observada;
**não identifica a versão do exporter que produziu o firmware**. Não é necessário
inventar um schema privado de inteiros de 32 bits. A leitura oficial permanece
limitada ao programa e é submetida à verificação estrutural nativa. O teste nativo
também exige rejeição de root fora do buffer, programa de tamanho inválido e
arquivo truncado.

`reference-schema-report.json` guarda a comparação independente. O workflow
subsequente também associa cada comparação ao SHA-256 do PTE decodificado e
registra versão da biblioteca e concordância/advertências por constante.

## Verificação final desta continuação

Run [36741368811](https://github.com/AkunDiscoRemake/MetaPort-HorizonOSPort/actions/runs/36741368811),
source `5d48c59`, relatório automático `7dd4e13`:

- dez verificações estruturais nativas aceitas e dez hashes de PTE conferidos;
- 35 constantes comparadas: 22 concordâncias diretas e 13 leituras Int64 nativas
  acompanhadas pela advertência de extensão do leitor conservador;
- os dois blobs DPE recuperados, com seis arrays de 22 escalas cada;
- teste sintético nativo aceito e três formas de buffer inválido rejeitadas;
- suíte tracking local: 28 testes, um pulado porque o binário nativo foi compilado
  no CI; o módulo nativo/sintético foi reexecutado no Actions após a compilação;
- regressões locais: suíte raiz 53 testes/um skip, guest 30 testes/um skip.

Dependências host-only ficam em `handtracking/ai/requirements.txt`. Para os
parsers e fixtures Python: `python3 -m unittest discover -s handtracking/ai/tests -v`.
O workflow gera os headers públicos e compila/testa o probe C++ separadamente.
A instalação local via apt não funcionou por falha de rede; a compilação C++
confirmada nesta etapa é a do runner, não uma build Android ou teste no telefone.

## Limites que permanecem

Aceitar a estrutura FlatBuffer não verifica a semântica dos kernels, índices de
controle de fluxo, executabilidade dos delegates, conteúdo dos segmentos opacos
ou compatibilidade da ABI privada. DPE/SKB/STP continuam referenciando
HexagonRpcBackend; não foi implementada sua execução no telefone.

Ainda faltam: conversão original do formato `v2`, crop/resampling e calibração,
execução neural compatível, reconstrução/filtragem das mãos, timestamps e
transporte para o tracking privado, integração de controles/poses e teste físico.
A UI original, compositor e lifecycle também não se tornaram portados por esta
análise. Não foi gerado um APK funcional nesta etapa.
