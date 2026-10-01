# Evidência e limites — UI/UX + passthrough

## Validação Android

Run **36802294948**: build AAR ARM64, testes Java, lint e testes nativos concluídos
com sucesso após adicionar `PassthroughRenderer`. Não é validação de câmera/shader
no aparelho. A implementação nativa do hand tracking continua sendo a mesma
biblioteca compartilhada pelo MetaPort.

## Primeira expansão da decompilação

Run **36802295037**, fontes reconstruídas (não código original exato):

| APK | Java gerados | Java com erros JADX | XML inventariados |
|---|---:|---:|---:|
| VrShell | 8013 | 35 | 878 |
| MetaSystemUI | 3143 | 10 | 4476 |

Ambos são `COMPLETED_WITH_ERRORS`: job concluído não significa todos os métodos
recuperados. Não compilar os resultados como se fossem os fontes oficiais.

A amostra mostrou um falso positivo importante: `passThroughShellCommand` e
`PassThroughHierarchyChangeListener` em MetaSystemUI **não são câmera**. Os cinco
matches da categoria passthrough desse APK nessa primeira execução são esses
casos. O scanner agora os exclui e prioriza comportamento sobre `R.java` e
`BuildConfig.java`. Relatórios gerados antes dessa correção mantêm a evidência
histórica, sem se transformar retroativamente em achados confirmados.

Em VrShell há referências à UI de saída de passthrough (toast de orientação e
recursos de ícones). Isso não estabelece o compositor, API de captura ou calibração.

## Análise ampliada e falha registrada

Run **36802376084** adiciona SystemUX, SettingsPanelApp e LibraryPanelApp, além dos
dois primeiros APKs; inspeciona todas as bibliotecas ARM64 embarcadas dentro dos
limites definidos. Foi iniciado antes da correção do filtro acima. Falhou na inspeção e na publicação; o motivo exato da inspeção ainda não foi
recuperado, pois o download dos logs falhou. Não foi tratado como sucesso.
A nova execução preserva falhas por APK, permite continuar após falhas do parser
ELF e atualiza o checkout antes de copiar relatórios para evitar conflito entre
execuções enfileiradas. Essa correção de publicação é preventiva, não uma causa
confirmada do erro anterior.

## Limites mantidos

UI original ainda NÃO PORTADA para um APK comum. Fundo de câmera está implementado
como componente ARCore/OES, mas NÃO conectado ao compositor Horizon. Não há
inferência completa de mãos MediaTek, reprojeção estéreo, depth ou teste físico.
Sem medidas de FPS/latência/temperatura não se declara otimização máxima.

O empacotamento incidental **36802294950** passou extração/verificação, mas falhou
na publicação da nova release; causa não confirmada (logs indisponíveis no sandbox).
A release de hand tracking anterior **36799154034** permanece a entrega publicada.
