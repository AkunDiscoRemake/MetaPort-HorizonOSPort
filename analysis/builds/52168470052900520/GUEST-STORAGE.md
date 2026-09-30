# Partições originais montadas e segundo estágio executado

**NOT PORTED YET: não há Home/System UI funcional nem APK pronto.**

> Este registro documenta o primeiro layout de armazenamento. Para o teste posterior
> com DT adaptado, misc e slots boot, veja [APK e serviços Meta](APK-AND-META-SERVICES.md).

## Evidência desta etapa

[Actions 36673917473](https://github.com/AkunDiscoRemake/MetaPort-HorizonOSPort/actions/runs/36673917473),
código `087fea4`, relatório publicado em `af8b2ea`: `guest-report.json`.
O experimento foi encerrado pelo supervisor após 180 segundos; não foi boot completo.

| Etapa | Resultado observado |
| --- | --- |
| Disco virtio/GPT | Reconhecido como vda, quatro partições físicas, 3.544.186.880 bytes |
| metadata | Ext4 novo, descartável, montado pelo init original |
| super | Metadados Android LP 10.0 aceitos pelo liblp original |
| Partições lógicas | system_a, system_ext_a, vendor_a, odm_a, vendor_dlkm_a, odm_dlkm_a, product_a criadas |
| Montagens originais | /system, /system_ext, /vendor, /odm, /vendor_dlkm, /odm_dlkm, /product: sucesso |
| Init | Primeiro estágio e **segundo estágio originais executados** |
| SELinux | Política original carregada; há negações com permissive=0 nos logs |
| Serviços | Tentativas de iniciar serviços originais, incluindo gerenciadores Binder, vold, keystore2 e HALs |
| Progresso final | Espera repetida por android.hardware.boot@1.0::IBootControl/default até encerrar o teste |
| Horizon / APK / telefone | Não demonstrado; nenhum teste físico nem alteração no telefone |

Trechos do relatório:

```text
[    7.120594] init: [libfs_mgr] __mount(source=/dev/block/dm-7,target=/system,type=ext4)=0: Success
[    7.127494] init: Switching root to '/system'
[    7.844089] init: [libfs_mgr] __mount(source=/dev/block/dm-13,target=/product,type=ext4)=0: Success
[   10.997834] init: Loading SELinux policy
[   13.157665] init: init second stage started!
[   47.305001] init: starting service 'servicemanager'...
[   54.578648] init: starting service 'vold'...
[   82.294375] init: starting service 'keystore2'...
[  178.000152] HidlServiceManagement: Waited one second for android.hardware.boot@1.0::IBootControl/default
```

**“starting service” não prova que um HAL terminou de inicializar ou está funcional.**
Não foi implementado serviço falso que apenas retorna sucesso para satisfazer essa espera.

## Implementação adicionada

- `guest/storage.py`: gera GPT primária/backup com CRC32 e super com geometria,
  tabelas LP, checksums SHA-256 e cópias de metadados. Verifica novamente os hashes
  dos arquivos originais enquanto os copia para as extensões do disco guest.
- Imagens originais de sete filesystems e vbmeta/vbmeta_system são copiadas sem
  alterações. O layout GPT/super é **novo para o guest**, não um dump do headset.
- metadata é um filesystem vazio gerado no runner. Não representa dados, contas,
  chaves ou provisionamento de um Quest. Não há userdata, vision ou misc neste layout.
- QEMU recebe apenas o arquivo de disco preparado, com `snapshot=on`; escritas do
  guest ficam em uma camada temporária. Sem mount no host, KVM, rede ou discos físicos.
- `guest/probe.py`: identifica eventos dos dois estágios, preserva montagens e
  tentativas de iniciar serviços, limita duração/console e não confunde workflow
  verde com Android completamente inicializado.
- `guest/avb_boot.py`: calcula parâmetros de passagem do bootloader a partir dos
  blocos vbmeta originais, com limites e validação estrutural. Não modifica flags,
  assinaturas, fstab, init ou SELinux.

O kernel continua sendo a fonte pública Meta adaptada documentada em
[GUEST-BOOT.md](GUEST-BOOT.md), **sem correspondência exata de fonte comprovada**
com esta publicação OTA. Os módulos originais continuam incompatíveis com sua ABI.

## AVB: o que mudou, e o que NÃO foi comprovado

No teste 36673195761, as partições lógicas já eram criadas, mas o libavb original
parava com `Invalid hash size` e `Failed to verify vbmeta digest`: faltavam os
parâmetros normalmente passados pelo bootloader.

A correção usa os blocos vbmeta reais, excluindo padding da partição:

- vbmeta: 5.632 bytes;
- vbmeta_system: 3.136 bytes;
- total: **8.768 bytes**;
- SHA-256 concatenado: `f5c659fe96a70b767ab1838646c6803db835c00d7f5cfb2345e8c3ace629c8bf`.

Esses valores alimentam `androidboot.vbmeta.hash_alg`, `.size` e `.digest`.
O guest passou dessa verificação e montou os filesystems sem desativar AVB/verity.
**Não há raiz de confiança Meta autenticada, estado de rollback em hardware nem
cadeia de boot segura reproduzida.** Um digest calculado pelo próprio runner não
substitui essas garantias. Também não foi declarado `verifiedbootstate=green`.

Referências de formato/comportamento:
- [AOSP LP metadata_format.h](https://android.googlesource.com/platform/system/core/+/android-14.0.0_r1/fs_mgr/liblp/include/liblp/metadata_format.h)
- [AOSP libfs_avb](https://android.googlesource.com/platform/system/core/+/android-14.0.0_r1/fs_mgr/libfs_avb/fs_avb.cpp)
- [AOSP AVB](https://android.googlesource.com/platform/external/avb/+/android-14.0.0_r1/)

## Bloqueios restantes observados

1. **BootControl HAL:** o caminho late-fs/checkpoint espera a interface HIDL original,
   que não fica disponível durante a janela de teste. Investigar serviço, dependências,
   logs e estado de slots/partições antes de escolher uma adaptação.
2. **Dados:** `/dev/block/bootdevice/by-name/userdata` não existe; o layout não inclui
   userdata/misc/vision e o alias bootdevice ainda referencia expectativas Qualcomm.
   Fstab exige criptografia com wrappedkey_v0; adicionar espaço vazio não resolve TEE.
3. **Hardware e módulos:** mensagens `disagrees about version of symbol module_layout`
   e espera por sysfs `oculus,nautilus/.../enable`. Não forçar módulos incompatíveis.
4. **TEE/KeyMint/Gatekeeper:** há tentativas de iniciar serviços; funcionamento e
   segurança não foram validados. Não fabricar chaves provisionadas ou atestação.
5. **Runtime/VR:** APEX/bootstrap e init não equivalem a Home, compositor, OpenXR,
   tracking, aplicativos ou desempenho VR. Integração no APK Android permanece pendente.

## Validação

Os testes cobrem checksums e limites GPT/LP, ordenação do digest AVB, padding,
footer fora dos limites, ciclos, flags de verificação desativada e separação dos
estágios de boot. No runner, `sgdisk --verify` também foi executado. A aceitação
pelo liblp original e as montagens efetivas são evidências independentes dos fixtures.
