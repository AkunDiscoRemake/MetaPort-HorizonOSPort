# Renderer original: aquisição de mesh, materiais e movimento

**Evidência estática; renderer/ABI/animações ainda NOT PORTED YET.**

Run [36778979923](https://github.com/AkunDiscoRemake/MetaPort-HorizonOSPort/actions/runs/36778979923)
concluiu com sucesso e recuperou 22 funções em `hand-render-decompilation.json`.
Biblioteca `libshell.so`, SHA-256
`2d4c274bc81c9f545f3b5571ba57643a9696333e8f6b3a125e45682fbd96dce0`.
A análise automática foi limitada a 900 segundos; sucesso não significa análise
completa nem execução original. Todos os endereços abaixo são **Ghidra**, com
image base `0x100000`; subtrair esse base para obter VAs ELF deste binário.

## Caminhos recuperados

| Função | Observação no C-like, não assinatura privada validada |
|---|---|
| `FUN_01c931f4` / `FUN_01c93770` | Resolvem `xrGetHandMeshFB`, consultam contagens, preparam buffers e fazem segunda chamada para preenchimento. |
| `FUN_00ecdf78` | Caminho que referencia localização de joints; inclui código de estado e chamadas OpenXR. |
| `FUN_01537fb8` | Componente de integração de avatar verifica 26 joints (`0x1a`) e atualiza hierarquia. Isso não converte automaticamente os 19/22/79/17 elementos dos assets de tracking. |
| `FUN_0110eda8` | `CoHandRenderBehavior`, exige dispositivo associado; referência explícita a cálculo de distância com `PokeInteractionComponent` e `CrossfadeDistance`. Não há fórmula temporal validada. |
| `FUN_00aba178` | **GhostHandRenderingSystem**, parâmetros de material, transformações e `sbSkinningMatrices`. Não presumir que todos os caminhos de mãos rastreadas usem as mesmas regras. |
| `FUN_013c39cc` | Preparação de dados de mesh, com rejeição de índice de mão inválido. |

Na função de ghost hands aparecem também:

- `ShellHandOutlineMaterial.u_outlineOpacityRange`;
- `ShellHandOutlineMaterial.u_outlineAlphaFade`;
- `ShellHandOutlineMaterial.u_outlinePinchParams`.

O código reconstruído replica um valor de fade nos quatro componentes do uniforme.
Os valores vêm do estado recebido; não foram substituídos por poses, confiança ou
animações inventadas. A sequência de conversão de transforms ainda depende de
helpers e constantes de matriz não recuperados integralmente.

### Constantes observadas, sem inventar semântica de lado

Argumentos compactados de 64 bits passados ao auxiliar de material:

| Uniforme | ramo índice zero | ramo índice não zero |
|---|---|---|
| `u_opacityRange` | `0x3d75c28fbc75c28f` | `0xbd75c28f3c75c28f` |
| `u_outlineOpacityRange` | `0x3c23d70a3ba3d70a` | `0xbc23d70abba3d70a` |

São evidências da reconstrução, não uma ABI de uniforms pronta para upload.
Não se atribuiu esquerda/direita, unidade de distância ou layout do objeto privado
apenas pelo número do índice.

## Problema detectado antes de transcrever o renderer

Ghidra marcou chamadas a `__wrap__ZdlPv` como não retornantes em diversos caminhos.
Isso pode eliminar caminhos do C-like, por exemplo após realocar/liberar vetores.
Não se deve copiar esses caminhos como implementação correta, nem remover a
anotação sem verificar o wrapper e suas instruções.

O coletor agora registra prefixos de listing de até 128 instruções, até 64 callees,
flags de truncamento e a indicação `analysis_no_return`. As flags descrevem a
análise, não contratos comprovados do binário. Nenhum protótipo foi forçado.

A próxima passagem prioriza os auxiliares observados de transformação, atualização
de material, buffer de skinning, visibilidade e hierarquia. Seus endereços são
aceitos apenas sob o hash fixo do renderer; não são apresentados como exports.

## Factory do modelo de mãos

Run [36779332456](https://github.com/AkunDiscoRemake/MetaPort-HorizonOSPort/actions/runs/36779332456)
concluiu com sucesso com 32 funções de entrada. O caller `FUN_0170dc50` seleciona
entre os construtores `FUN_017222a0` e `FUN_01717b90`, em ramos com alocações de
`0x230` e `0x288` bytes. O significado do seletor ainda não foi estabelecido;
não é prova de fallback CPU, de compatibilidade MediaTek ou de conversão de pixels.
A passagem seguinte inclui o outro construtor e suas strings de identificação.

O histórico 36777058920 continua sendo um run falho. O novo run bem-sucedido
verificou a correção do gate sem reescrever aquele resultado.
