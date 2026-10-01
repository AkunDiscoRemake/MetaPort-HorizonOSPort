# Conversões de payload espacial recuperadas — componente parcial

`space_data.cpp` adapta quatro corpos originais de
`libhzos_spaces.meta.so`, SHA-256
`3084f8873424783e9a1719cb135c9f5b20396d4aca54e8d2b2136469758a50b0`.
Evidência: `shell-hzos-spaces-native.json`, run **36809949550**.

| Conversor original / VA ELF | Cabeçalho de destino observado | Cópia observada |
|---|---|---|
| toHzuSpaceData / 0x2ea0 | palavra inicial 0x55 | 0x74 bytes para destino +8 |
| toHzuBaseSpaceData / 0x3b20 | palavra inicial 0xcb | 0x74 bytes para destino +8 |
| toHzuVirtualSpaceData / 0x3c30 | palavra 0: 0xcb; palavra +4: 1 | 0x10 bytes para destino +8 |
| toHzuWindowSpaceData / 0x3cc0 | palavra 0: 0xcb; palavra +4: 2 | 0x14 bytes para destino +8 |

Offsets em bytes, conferidos na listagem ARM64 (não inferidos do tamanho de um
ponteiro C-like). A rotina legacy lê até origem +0x70 e escreve até destino +0x78,
quatro bytes nessa última operação. Isso estabelece extensão escrita 0x7c, **não
sizeof da estrutura privada**. Tipos, unidades, timestamps e flags dos campos
permanecem sem interpretação suficiente para criar uma pose ARCore equivalente.

A adaptação tem API própria: `metaport::spaces::copy_payload`, não exporta nomes
Hzu nem declara ABI privada compatível. Não recebe poses geradas artificialmente.
A cópia mantém bits exatos, inclusive padrões NaN, sem cálculo sobre floats.
Cabeçalho, padding e restante do destino são preservados. Buffer nulo, tamanho
insuficiente, cabeçalho incompatível ou sobreposição são recusados sem escrita.
Os limites e a recusa de sobreposição são proteções adicionais do adaptador;
a semântica original para buffers inválidos/sobrepostos não é alegada equivalente.
Os estados `CopyStatus` não são os códigos de retorno da API privada Meta.

O componente participa do build nativo MetaPort. Isso não significa que já esteja
conectado ao consumidor original: serviço de espaços, handles, transformações,
referenciais, relógios e produtor ARCore continuam pendentes.

`native/tests/space_data_test.cpp` testa 256 padrões por layout, alinhamento,
cabeçalhos preservados, limites e rejeição de sobreposição. CI executa host com
ASan/UBSan e binário ARM64 sob QEMU. São testes da implementação adaptada, não um
oráculo executando a biblioteca proprietária, nem teste de 6DoF no aparelho.
