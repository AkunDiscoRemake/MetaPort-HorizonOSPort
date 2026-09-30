# Adapters Android do MetaPort

**Backends implementados e compilados; integração Horizon: NOT PORTED YET.**
Não há Activity, launcher, UI parecida com Horizon, compositor falso ou poses de demo.
O produto deste módulo é uma biblioteca **AAR**, não um APK instalável.

## Implementações reais

| Backend | Implementação | Limites explícitos |
| --- | --- | --- |
| `NativeSensors` | Fila de eventos Android NDK em thread própria; rotation vector, gyro, accel; cache C++ sincronizado | Orientação 3DOF apenas; sem posição fabricada, sem callback Horizon |
| `ArCoreTracking` | Session/Frame reais, pose de câmera 6DOF, tracking state/failure reason, planos, anchors locais | Depende de suporte ARCore e câmera liberada; sem confiança numérica inventada, floor inferido, head pose ou hand tracking |
| `EglOutput` | ANativeWindow/EGL, GLES3→GLES2, swap interval e timestamp de apresentação quando suportado | É saída de superfície, não o compositor Horizon; Vulkan, layers, distorção e reprojeção não implementados |

O suporte ARCore do Infinix X6873 não foi confirmado. Compilar não significa que o
serviço ARCore aceite o dispositivo nem que a câmera funcione dentro do VRBox.

## Build e testes

Toolchain fixada: Gradle 8.10.2, AGP 8.7.3, Java 17, SDK 35, NDK 27.2.12479018,
CMake 3.22.1, ARCore 1.48.0. Min Android API 29, ABI arm64-v8a.
A biblioteca nativa usa alinhamento ELF de 16 KiB; isso não certifica dependências
externas ou binários originais para aparelhos com páginas de 16 KiB.

```sh
gradle -p port/android :adapters:assembleRelease \
  :adapters:testReleaseUnitTest :adapters:lintRelease
```

Actions: `.github/workflows/build-adapters.yml`. Artifact:
`metaport-android-adapters-arm64`, retenção 7 dias. Relatório pequeno:
`analysis/android-build/build-report.json`. Não há firmware original no AAR.

Testes nativos no host (cache, normalização, timestamps, invalidação e concorrência):

```sh
mkdir -p local-analysis/native-tests
g++ -std=c++17 -Wall -Wextra -Werror -pthread -fsanitize=address,undefined -g \
  -Iport/android/adapters/src/main/cpp native/tests/sample_cache_test.cpp \
  -o local-analysis/native-tests/sample_cache_test
local-analysis/native-tests/sample_cache_test
```

Testes JVM cobrem somente `PoseData`. **Ainda não foram testados sensores NDK,
ARCore, câmera ou EGL em aparelho físico/instrumentação Android.**

## Integração no APK hospedeiro futuro

Preferir dependência de projeto Gradle. Para consumir um AAR solto, declarar também
`implementation 'com.google.ar:core:1.48.0'`: dependências Maven não são embutidas no
AAR. Não basta renomear AAR para APK.

### Sensores

Criar `NativeSensors` com Context do aplicativo. `start(10000)` solicita 100 Hz;
a frequência efetiva depende do hardware. Retorno é o bitmask dos sensores que o
Android realmente habilitou. `snapshot(maxAgeNs)` invalida amostras antigas e não
substitui sensores ausentes. Chamar `stop()` ao pausar e `close()` ao encerrar.
Não há wake lock, coleta de câmera nesse backend nem permissão de sensor de alta taxa.
Chamadas de start/stop podem esperar inicialização/join; não colocá-las no caminho
crítico de composição de frames. Estado inválido produz arrays null.

### Tracking ARCore e saída EGL

1. O host verifica `ArCoreTracking.availability(context)`. UNKNOWN é inconclusivo,
   não suporte. Solicitar instalação somente por ação explícita, na thread UI.
2. O host solicita permissão CAMERA e verifica concessão antes de criar sessão.
3. Na thread de renderização proprietária, criar `EglOutput` sobre uma Surface válida.
   Ele possui seu próprio EGLDisplay/contexto; não compartilhar ownership com outro
   gerenciador EGL. Nenhuma janela ou UI é fabricada por essa classe.
4. No contexto atual, criar/bind uma textura `GL_TEXTURE_EXTERNAL_OES` com
   `glGenTextures`/`glBindTexture`, e passá-la a `ArCoreTracking.setCameraTexture`.
   Configurar geometria de display, resume e chamar update com o contexto atual.
5. A pose fornecida é world-from-physical-camera, em metros, xyzw. Não é eye/head
   pose. Não reutilizar o último frame como tracking válido após erro/pause.
   `newCameraFrame=false` indica timestamp repetido; não inventa aquisição nova.
6. O backend não desenha a câmera. Passthrough só estará integrado quando o
   compositor original puder consumir a textura e sua geometria corretamente.
7. Ao pausar: parar sensores e pausar ARCore antes de destruir a Surface/contexto.
   Ao recriar contexto: recriar textura e informá-la à sessão. Ao encerrar: detach
   anchors, close ARCore, remover textura e close EGL na thread proprietária.

Não abrir Camera2 em paralelo: este backend usa a câmera exclusiva do ARCore.
Uma solução SharedCamera/mãos requer arbitragem própria, ainda não implementada.

## Relógios e coordenadas: não misturar

- Sensores NDK: timestamp Android baseado em BOOTTIME, comparado com
  `SystemClock.elapsedRealtimeNanos()`. Eixos naturais do dispositivo Android.
- ARCore: timestamp do Frame, mantido como domínio separado. Não assumir que seja
  intercambiável com o dos sensores ou com o runtime Horizon sem medir/converter.
- EGL presentation time: CLOCK_MONOTONIC. O host deve fazer a conversão necessária;
  zero omite o timestamp, e extensão ausente com timestamp solicitado gera erro.
- Confiança numérica, floor, recenter Horizon e extrínseca câmera→cabeça: não inferidos.

## O que falta do lado Horizon

O transporte observado usa MemoryBroker/Binder e regiões compartilhadas. Ver
[contrato observado](../../horizon/tracking/CONTRACT.md). Os símbolos, layouts e
lifecycle originais não foram substituídos pelos tipos deste módulo. Não é correto
carregar este AAR e afirmar que o Horizon já está recebendo suas poses.

Hand tracking, passthrough integrado, Vulkan, OpenXR hardware bridge, áudio/input
originais e calibração óptica completa continuam **NOT PORTED YET**.
