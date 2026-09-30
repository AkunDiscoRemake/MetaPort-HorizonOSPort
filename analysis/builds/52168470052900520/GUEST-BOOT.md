# Primeiro estágio original executado em guest — não é boot completo

**NOT PORTED YET. Não há APK funcional nem Home/System UI em execução.**

> Registro histórico do primeiro experimento. Para o estado mais recente, veja
> [partições montadas e segundo estágio original](GUEST-STORAGE.md).

## Resultado medido

[Actions 36672348632](https://github.com/AkunDiscoRemake/MetaPort-HorizonOSPort/actions/runs/36672348632),
código `4bd35b1`, relatório publicado em `6762b14` (`guest-report.json`).

- Kernel oficial público da Meta, adaptado e compilado, executado em QEMU TCG.
- Ramdisks originais de boot/vendor_boot descompactados pelo kernel, sem trocar `/init`.
- **O `init` original executou seu primeiro estágio no caminho de boot normal.**
- O processo chegou à procura das partições necessárias e reiniciou por não encontrá-las.
- Não foram anexados discos de sistema neste experimento. Essa falha não prova que
  as imagens originais sejam defeituosas: o layout de armazenamento guest ainda falta.
- Sem rede guest, KVM, discos do host ou acesso ao telefone; nenhuma alteração no Infinix.

Trecho efetivamente observado:

```text
[    5.198982] Run /init as init process
[    5.671850] init: init first stage started!
[    5.924943] init: Switching root to '/first_stage_ramdisk'
[    6.973614] init: ... partition(s) not found in /sys, waiting for their uevent(s): metadata, super, vbmeta_a, vbmeta_system_a
[   16.991966] init: ... partition(s) not found after polling timeout: metadata, super, vbmeta_a, vbmeta_system_a
[   16.998692] init: Failed to mount required partitions early ...
[   17.022647] init: InitFatalReboot: signal 6
[   17.098483] reboot: Restarting system with command 'bootloader'
```

Esse último comando reinicia somente a máquina virtual. Não acessa o bootloader do telefone.
O retorno zero do QEMU e o workflow verde **não** significam Android inicializado:
o relatório registra `android_boot_completed: false`.

## Origem e adaptações

Fonte pública `facebookincubator/oculus-linux-kernel`, commit
`8f32bdea05abf85dd10d6202963f7e9bdc55c717`, publicação `5227074.3810.520`, Linux 5.10.240.
**Não é uma correspondência exata demonstrada com a fonte da build OTA 52168470052900520.**

O merge preserva as configurações anorak/eureka como base e aplica a diferença
`guest/kernel/virt.config`: console PL011, virtio MMIO/bloco, initramfs e filesystems.
CFI/LTO/SCS foram desativados para o experimento com LLVM 14 da distribuição.
Isso altera propriedades de segurança/desempenho; não é uma configuração de produção.

Imagem adaptada executada: **26.726.912 bytes**, SHA-256
`ccfab9201d01cf678a0bdc00cb910556b7b2e889a3e186f11ad4e4570f33fba1`.

Initrd concatenado vendor + generic, sem editar seus arquivos, SHA-256
`dc0ee2795c81bd0b426a791b9ec0544943900af95f351edbdee9124d24bd5118`.
Inventário: 492 entradas no boot e 144 no vendor_boot, ambos LZ4 legacy.
O `/init` é symlink para `/system/bin/init`; o binário tem 2.195.232 bytes e SHA-256
`2177327ab70348ce571c9d536dfbfbd93564d022d1b5d5dfcb84f5f39bbf1ddc`.

A máquina usa DT gerado pelo QEMU, CPU `max`, 2 CPUs e 1 GiB de RAM. A cmdline inclui
`androidboot.hardware=eureka androidboot.slot_suffix=_a androidboot.force_normal_boot=1`.
Não informa sucesso de AVB, não forja identidade provisionada e não desliga SELinux.
O bootconfig original ainda não é anexado; não há implementação completa do bootloader.

## Falhas localizadas e corrigidas no experimento

| Execução | Resultado |
| --- | --- |
| 36669917357 | Makefile Meta exigia `REAL_CC`; compilação parou antes do kernel. Corrigido. |
| 36670135460 | Kernel compilado; QEMU do runner não tinha CPU `cortex-a76`. Nenhum boot. |
| 36671280366 | Kernel executou com `cortex-a72`; init terminou com SIGILL antes do primeiro estágio. |
| 36672056650 | CPU `max` permitiu executar init, mas sem flags de boot normal entrou em recovery; recovery falhou repetidamente. |
| 36672348632 | Caminho normal confirmado; init aguardou metadata/super/vbmeta e reiniciou por falta dos discos. |

A mudança de CPU eliminou o SIGILL observado, mas a instrução exata responsável
não foi isolada; não se deve atribuir a falha a uma extensão ARM específica ainda.
O cache reutilizou a mesma imagem compilada nas duas últimas execuções.

## Próximas dependências concretas

1. **Armazenamento guest**: criar um layout virtual com metadata, super e vbmeta
   por slot, incorporando as imagens originais já reconstruídas. O OTA contém
   partições lógicas individuais, não uma imagem super pronta nem userdata provisionada.
2. **Módulos**: o init tentou carregar `kfifo_buf.ko`, mas o kernel registrou
   `disagrees about version of symbol module_layout`. A carga de `ak09973` também
   falhou. Não forçar módulos ABI-incompatíveis; distinguir drivers físicos sem
   dispositivo correspondente de funções realmente necessárias no guest.
3. **Fstab/AVB**: o fstab original exige partições lógicas e AVB para system,
   system_ext, vendor, odm, vendor_dlkm, odm_dlkm e product. As assinaturas ainda
   não foram autenticadas pelo projeto. Não relatar AVB como aprovado.
4. **Dados/TEE**: o fstab pede `wrappedkey_v0`, criptografia de metadata/userdata/vision
   e caminhos da controladora UFS Qualcomm. Isso exige adaptação explícita; não
   existem chaves ou dados provisionados do headset disponíveis neste projeto.
5. Depois da montagem ainda faltam serviços vendor, runtime/compositor originais,
   pontes para os backends Android, gráficos, tracking, entrada e empacotamento APK.
   Executar init em runner x86 não valida desempenho VR nem funcionamento no X6873.
