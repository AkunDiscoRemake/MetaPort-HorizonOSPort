# Mapa inicial de portabilidade — build 52168470052900520

**Estado: NOT PORTED YET.** Análise estática real; não houve boot, execução de
componentes Horizon nem validação em smartphone. Escopo: [declaração vigente](../../SCOPE.md).

Última execução analisada: [36665649596](https://github.com/AkunDiscoRemake/MetaPort-HorizonOSPort/actions/runs/36665649596),
script no commit `d9d28a4`. Evidências locais:
[reconstruction.json](reconstruction.json) e [static-analysis.json](static-analysis.json).

## Resultados medidos

- Reconstruídas `system`, `system_ext`, `vendor`, `product`, `odm`, com verificação
  dos SHA-256 de todas as operações e de cada imagem final. Cinco imagens ext4.
- 6.260 entradas de filesystem inventariadas nessas partições e 40 adicionais nos
  três módulos APEX Meta: total 6.300 (arquivos, diretórios, symlinks etc.).
- APEX `com.meta.xr`, `com.meta.quest` e `com.meta.hzos` inspecionados sem mount.
- Cinco APKs: manifestos XML binários lidos com aapt, conteúdo DEX apenas enumerado.
- 86 ELF analisados estaticamente: cabeçalhos, dependências DT_NEEDED, seções,
  amostras de símbolos dinâmicos; 82 amostras limitadas de disassembly AArch64.
  Quatro ELF ARM32 não foram desassemblados. Um candidato era script, não ELF.
- Não houve decompilação DEX, disassembly completo ou inferência completa de ABI.
- Imagens e componentes são temporários no runner. Somente relatórios vão ao Git.

## Componentes localizados de fato

| Componente observado | Localização no conteúdo original | Estado |
| --- | --- | --- |
| System UI | `system_ext:/priv-app/MetaSystemUI/MetaSystemUI.apk`, pacote `com.meta.systemui` | Manifesto analisado; NOT PORTED YET |
| Shell | `system_ext:/priv-app/VrShell/VrShell.apk`, pacote `com.oculus.vrshell` | Manifesto e bibliotecas selecionadas; NOT PORTED YET |
| Driver/runtime package | `com.meta.xr:/priv-app/VrDriver/VrDriver.apk`, pacote `com.oculus.systemdriver` | Manifesto e bibliotecas selecionadas; NOT PORTED YET |
| Tracking | `odm:/bin/trackingservice` | ELF e declaração init; NOT PORTED YET |
| Compositor vendor | `system_ext:/bin/hw/vendor.oculus.hardware.composer-service` | ELF e declaração init; NOT PORTED YET |
| Integração SurfaceFlinger/XR | `system:/system/bin/surfaceflinger`, `system:/system/lib64/libxrsurfaceflinger.so` | ELF e dependências; NOT PORTED YET |
| Presença | `com.meta.quest:/priv-app/PresenceService/PresenceService.apk` | Manifesto e bibliotecas selecionadas; NOT PORTED YET |

## Entrada OpenXR comprovada pelo manifesto

`com.meta.xr:/active_runtime.aarch64.json` declara:

```
/apex/com.meta.xr/priv-app/VrDriver/VrDriver.apk!/lib/arm64-v8a/libopenxr_forwardloader.so
```

A biblioteca `libopenxr_forwardloader.so` exporta
`xrInitializeLoaderKHR` e `xrNegotiateLoaderRuntimeInterface`; importa `dlopen`,
`dlsym` e `android_dlopen_ext`. Isso comprova a existência desses símbolos, não que
a inicialização seja possível no Android do telefone.

No mesmo APK, `libvrapiimpl.so` exporta `xrGetInstanceProcAddr`,
`xrNegotiateLoaderRuntimeInterface`, `xrInitializeLoaderKHR`, `JNI_OnLoad` e
`ovr_GetPrivateAPIFunction`. Depende, entre outras, de `libhzos.meta.so`,
`libhzos_featurejournal.meta.so` e `libhzos_gaze.meta.so`.

`libvrruntimeservice.so` depende de `libhzos.meta.so`, `libhzos_spaces.meta.so`,
`libhzos_gaze.meta.so`, `libbinder_ndk.so`, `libstatssocket.so`, EGL/GLES e outros.
Não se concluiu ainda qual biblioteca o forwardloader seleciona em cada condição.
É preciso seguir os call sites de carregamento e negociação, não apenas nomes.

## Dependências impeditivas de uma cópia direta para APK

Evidência em `configuration[].services`:

- `trackingservice`: `user system`, grupos `system uhid inet audio`, `SYS_NICE`.
- `trackingfidelityservice`: `user system`, grupos `system camera`.
- compositor Oculus: `user system`, grupo `graphics`, `SYS_NICE`.
- compositor QTI: `user system`, grupos `graphics drmrpc`, `SYS_NICE` e socket `pps`.

Evidência nos ELF:

- `libhzos.meta.so` usa Binder, HIDL, FMQ, `libgui`, `libui`, câmera e áudio de
  plataforma, além de bibliotecas específicas do sistema original.
- serviço de sensores Oculus depende de câmera/calibração, clock sync, syncboss,
  interfaces HIDL/FMQ e implementações vendor.
- tracking client/host usam `libmemorybrokerclient.so` e Binder NDK.
- compositor usa interfaces de display/mapper vendor e bibliotecas de plataforma.

APK comum não recebe UID system, capacidades de processo e serviços vendor do
headset. Copiar bibliotecas com nomes iguais não garante ABI nem acesso Binder.
A emulação de CPU por si só não fornece os dispositivos e serviços que elas esperam.

## Próximos contratos a recuperar antes de escrever adapters

1. **Loader:** call sites de `dlopen`/`android_dlopen_ext`/negociação, nomes de
   bibliotecas, namespaces e inicialização JNI. Registrar símbolos e endereços reais.
2. **IPC:** identificar descriptors e chamadas Binder/AIDL/HIDL usadas por
   `libvrruntimeservice`, `libhzos.meta` e memory broker; ownership e transporte de
   buffers, fences, handles e erros. Não inventar respostas de sucesso.
3. **Tracking:** seguir aquisição e sincronização das amostras no serviço real;
   recuperar unidades, clocks, coordenadas e contratos de confiança antes de ARCore.
4. **Display:** distinguir compositor de aplicação, SurfaceFlinger e HAL; mapear
   gralloc/mapper, EGL/Vulkan, fences e timing para uma superfície Android do APK.
5. **Java:** decompilar DEX selecionados dos pacotes originais e levantar serviços,
   permissões, lifecycle e dependências de framework; não substituir por launcher.
6. **Decisão de runtime:** escolher guest completo, userspace com bridges ou híbrido
   somente depois desses contratos. Ainda não há guest inicializável nem adapter.

## Limites de confiança

Hashes conferidos contra metadados não autenticam a origem perante uma chave Meta.
APKs/APEX não tiveram assinaturas autenticadas. Identificação comercial/canal continua
incerta, mas deixou de ser bloqueio de escopo com a autorização ampliada informada.
A seleção de binários é limitada e priorizada por nome: não é uma análise completa.
As imagens foram reconstruídas em disco temporário do runner e não são preservadas
como firmware no Git. A coleta é reproduzível, mas envolve novo download.
