# Compatibilidade pública e requisitos preliminares

**Ainda não existe APK Horizon funcional validado. Nenhum aparelho está certificado
pelo MetaPort. Os números abaixo são alvos de engenharia para a primeira alfa,
não mínimos medidos, garantia de compatibilidade ou recomendação de compra.**

## Requisitos / orçamento para testes

| Item | Mínimo atual ou alvo de entrada | Recomendado para testar a futura alfa |
|---|---|---|
| Android | Android 10/API 29: piso do build dos **adaptadores**, não do Horizon original | Android 14/API 34 ou superior, com drivers atualizados e ARCore suportado |
| Arquitetura | Android e processo ARM64 (`arm64-v8a`); único ABI Android entregue hoje | ARM64; SoC com capacidade sustentada a validar, independentemente de marca |
| RAM física | **Alvo:** 6 GB; mínimo funcional desconhecido | **Alvo:** 12 GB; RAM virtual/expansão não substitui RAM física |
| Espaço livre | **Orçamento inicial:** 4 GB, não tamanho previsto do APK | **Orçamento:** 8 GB; imagens de firmware e ferramentas de análise não irão no APK |
| GPU | Driver EGL/GLES compatível com o pass OES e com ARCore; confirmar em teste | GPU/driver moderno com folga térmica; Vulkan não é requisito implementado do renderer atual |
| Tela | **Alvo:** menor dimensão de 1080 pixels e 60 Hz | 1080 pixels ou mais, 90 Hz ou mais; taxa de tela **não garante FPS** |
| Câmera/sensores | Câmera traseira desobstruída, giroscópio/acelerômetro e ARCore operacional para 6DoF | Mesmos requisitos; boa exposição, sincronização e desempenho sustentado |
| Profundidade | Depth API suportada no **modo solicitado**, se essa função for usada | Validar AUTOMATIC e RAW separadamente; sensor dedicado não é exigido pelo código MetaPort |
| Suporte VR | VRBox/Cardboard compatível com dimensões, foco e câmera do aparelho | Câmera livre, encaixe estável e ventilação; calibração óptica ainda precisa ser validada |
| Internet | Análise e uso local não exigem conta Meta; instalação de dependências pode precisar de rede | Rede estável para futuros serviços online autorizados; estes ainda não funcionam no port |

Não há lista confiável de chips mínimos para o runtime original enquanto não houver
inferência e compositor funcionando e medidos. GHz, número de núcleos e marca do
SoC não substituem testes. Não exigir Qualcomm ou prometer que todo MediaTek
funcionará. O Android precisa ser 64-bit: ter CPU de 64-bit com sistema 32-bit não basta.

## Compatibilidade por capacidade, não “universal”

1. ARCore disponível não implica suporte a Depth. Consultar por modelo/OS e em
   execução, usando `isDepthModeSupported` para cada modo solicitado.
2. Compatibilidade ARCore não certifica Horizon, modelos de mãos, serviços Meta
   ou qualidade de VR. Infinix X6873 continua **não validado fisicamente**.
3. Sem 6DoF não anunciar 6DoF; sem depth, desabilitar recursos dependentes dele e
   informar indisponibilidade. Não inventar pose, profundidade ou confiança.
4. ARCore pausado/perdido deve invalidar pose para conteúdo ancorado. Imagens antigas
   não são prova de passthrough ao vivo. Não usar esta alfa para navegação segura.
5. Não bloquear a aplicação por marca, presença de root ou formato de visor.
   A verificação de capacidade é específica da função; não é detector de root/VR.
6. Root, desbloqueio e flash não fazem parte da instalação. Métodos que dependem de
   permissões signature/privileged não ficam disponíveis só por recompilar o APK.

[Lista oficial ARCore](https://developers.google.com/ar/devices) ·
[Depth API](https://developers.google.com/ar/develop/java/depth/developer-guide).
Estas fontes devem ser consultadas novamente na hora de testar; não são uma
lista de aparelhos aprovados pelo MetaPort.

## Matriz pública: critérios para aprovar um aparelho

Registrar, com consentimento e sem coleta automática de identificadores pessoais:
modelo e variante, Android/API, driver/ABI, versão do app/ARCore, páginas 4/16 KiB,
modo de depth disponível e resultados reais por função. Não pedir IMEI, serial,
conta, tokens, fotos da casa nem dados biométricos como relatório público.

Exigir teste de 30 minutos para observar aquecimento/throttling, registrar frame
time p50/p95/p99, memória máxima, perdas de tracking, estabilidade de câmera e
pause/resume/revogação de permissão. Separar tempos CPU/GPU/inferência de refresh
da tela. Esse protocolo é planejado, não medição já realizada.

Incluir pelo menos Adreno e Mali, múltiplos fabricantes, Android/API e tamanhos de
página antes de dizer que a versão tem suporte amplo. Publicar também falhas e
recursos indisponíveis. Sem amostra física, manter a classificação “não testado”.

## Distribuição pública

Código próprio é GPL-3.0-only. Modelos, apps e assets Meta não se tornam GPL por
estarem junto do projeto. A autorização relatada pelo solicitante não foi
verificada; antes de ampliar redistribuição pública, confirmar por escrito o
escopo (binários, modelos, marcas e uso dos serviços). Não apresentar como produto
oficial ou certificado pela Meta. Popularidade não altera esses requisitos.

## ABI ARM64 não basta para os binários originais

A análise e execução de 2026-10-01 encontraram instruções LSE e RCpc em
`libc++.so` do firmware. No experimento isolado **36900295491**, o tradutor do
emulador API 36 executou o controle e `ldaddal`, mas `ldaprb` provocou SIGILL.
Isso é uma limitação demonstrada desse ambiente, não um teste do Infinix nem uma
prova de que todo aparelho anunciado como ARM64 executará o firmware.

Uma adaptação pontual de acquire está sendo testada separadamente, com hashes e
instruções alteradas declarados em `horizon/ui/RCPC-EXPERIMENT.md`. Não há detecção
física de extensões, comparação de desempenho, certificação ARCore/Depth ou novo
modelo de telefone aprovado por esse experimento. Os requisitos públicos continuam
preliminares; não anunciar compatibilidade universal a partir da instalação do APK.
