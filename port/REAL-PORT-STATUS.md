# Marco: primeiro APK original funcional (ainda não atingido)

Não publicar demo, launcher/WebView ou biblioteca AAR como “Quest completo”.
AAR é componente de build; não é aplicativo instalável.

| Área | Implementado/recuperado | Bloqueio para o marco |
|---|---|---|
| UI/configurações | Decompilação original de cinco APKs; manifesto, JNI, Binder e recursos | Recompilar/ligar código original, resolver classes privadas e permissões; erros JADX e arquivos omitidos explicitamente |
| Mãos | 21 containers originais, dez PTE descomprimidos; módulo nativo compartilhado | Inferência DPE usa HexagonRpcBackend; falta backend compatível no MediaTek, formatos/calibração e comparação numérica |
| Passthrough | Pass OES da câmera ARCore, sem readback de imagem para Java | Ligar ao compositor original; não há captura estéreo/reprojeção/oclusão Quest |
| Depth Android | Aquisição real opcional AUTOMATIC/RAW, confiança raw e timestamps, leitura com stride | Suporte e validação física no Infinix; não é algoritmo Meta |
| Depth Quest | Dois modelos mldepth e tuning localizados; inspeção original iniciada | Consumidor, entradas, calibração, kernels e execução original não recuperados integralmente |
| Store/cloud | Extração/decompilação dos clientes originais iniciada | Backend Meta, fluxo autorizado de autenticação, entitlement e permissões reais; não reproduzidos por APK |

Build Android **36805393417: sucesso** após implementação de depth, incluindo testes
Java e lint. Isso não mede câmera/depth/shader no aparelho.

Execuções iniciadas nesta etapa:
- UI/configurações: **36805504164**.
- Store/identidade/DeviceAuth/OCMS/social: **36805504240**.
- Modelos depth originais: **36805607831**.

## O que bloqueará a alegação de APK funcional

Exigir boot do cliente original, apresentação original, entrada real e teste de
ciclo pause/resume no aparelho. Habilitar mãos somente após resultados reais da
inferência original; depth somente com dados de origem identificada. Cada função
de configuração deve ter seu efeito real comprovado, não apenas botão visível.
Store exige catálogo/autenticação/entitlement reais por integração autorizada;
não simular compras nem contornar assinaturas/atestação ou permissões do Android.

O sensor/câmera ausente não é criado pelo VRBox. APIs signature/privileged não
ficam disponíveis a APK comum só por recompilar. Alguns recursos podem exigir
cooperação da Meta/fabricante ou ser inviáveis sob o requisito de APK sem
privilégios e bootloader bloqueado. “Ainda não portado” não é promessa de que
todo recurso do Quest poderá ser reproduzido nesse hardware.

## Atualização: revisão dos jobs e preparação para público

Os runs UI **36805504164** e cloud **36805504240** terminaram com sucesso de análise,
com erros/omissões de decompilação descritos em `docs/PORTING-METHOD.md`. Isso não
altera os bloqueios de execução da tabela acima. O run depth **36805607831** também
terminou; o formato dos modelos permanece opaco (TH1).

Requisitos preliminares: `docs/COMPATIBILITY.md`; política verificável em
`devices/compatibility-policy.json`. Nenhum modelo de telefone validado fisicamente,
sem promessa de compatibilidade universal ou APK completo.

## Inicialização original: progresso sem APK funcional

A análise 36812219346 recuperou a cadeia da thread até `ShellApp` e seu laço de
frames. Há dependências explícitas de identidade, Clay e plataforma VR antes do
loop; o encerramento do serviço inclui `_Exit(0)`. A ligação JNI agora tem tipos
C++ gerados das declarações do DEX original, incluindo retorno `jlong` de
`nativeInit`, com checagem NDK adicionada ao build. Esses tipos não implementam
serviços nem tornam o shell carregável. Ver `horizon/ui/STARTUP-BRIDGE.md`.

O próximo alvo de análise é a inicialização da plataforma e a iteração de frame,
não empacotar um launcher substituto. A exigência de APK comum continua sujeita
aos bloqueios de serviços/permissões listados acima; não há garantia técnica de
portar integralmente o Horizon nesse regime.
