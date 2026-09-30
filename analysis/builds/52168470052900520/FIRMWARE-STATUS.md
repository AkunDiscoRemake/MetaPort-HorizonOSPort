# Firmware original completo: reconstrução concluída, port não concluído

**MetaPort não é um launcher ou demo. Objetivo: software original em ambiente guest
adaptado ao Android/VRBox. Estado do sistema portado: NOT PORTED YET.**

Não foi criado um APK hospedeiro vazio para substituir esse objetivo.
A biblioteca Android/NDK existente é infraestrutura auxiliar, não o Horizon OS.

## Atualização: primeiro estágio em máquina virtual

O [experimento de boot guest](GUEST-BOOT.md) compilou um kernel público Meta
adaptado e executou o init original no caminho normal. O init parou por falta
de metadata/super/vbmeta no hardware virtual. **Não houve boot completo nem APK.**
A fonte pública selecionada não é uma correspondência exata comprovada com o OTA.

## Resultados da análise estática

- Reconstruídas **todas as 29 partições declaradas no OTA**.
- Total de imagens: **3.739.418.624 bytes**, verificadas contra os hashes de saída.
- Todas as operações de reconstrução tiveram seus hashes verificados.
- Boot e vendor_boot v4 identificados; kernel e configuração embutida inspecionados.
- Disassembly completo da seção `.text` de bibliotecas menores de IPC e do
  `libopenxr_forwardloader.so`, dentro dos limites do analisador. Isso NÃO significa
  disassembly completo de todo o OS nem recuperação de seu código-fonte.
- Serviço Binder original, parte do protocolo e VINTF identificados por evidência.

Relatórios: `reconstruction.json`, `static-analysis.json`.
Contrato recuperado: `horizon/tracking/abi/52168470052900520.json` na raiz do projeto.

“Todas as partições do OTA” não quer dizer dump de todo armazenamento de um headset:
não inclui necessariamente dados provisionados por unidade, contas, userdata ou
segredos de hardware. Não foram obtidos nem fabricados esses dados.

## Firmware: matriz de cobertura

| Grupo | Partições reconstruídas | Análise realizada | Port |
| --- | --- | --- | --- |
| Android userspace | system, system_ext, vendor, product, odm | Inventários, seleção de ELF/APKs/APEX e serviços | NOT PORTED YET |
| Kernel / boot | boot, vendor_boot | Cabeçalhos, kernel, configuração, cmdline, tamanhos | NOT PORTED YET |
| Módulos vendor | vendor_dlkm, odm_dlkm | Inventário de filesystem | NOT PORTED YET |
| Verified Boot | vbmeta, vbmeta_system | Identificação do formato; assinaturas não autenticadas | NOT PORTED YET |
| Device tree | dtbo | Reconstrução/hash; estrutura interna não interpretada | NOT PORTED YET |
| Firmware auxiliar | abl, adsp, aop, aop_config, cpucp, devcfg, featenabler, hyp, imagefv, keymaster, qupfw, shrm, tz, uefi, uefisecapp, xbl, xbl_config | Identificação básica quando reconhecida; não executados | NOT PORTED YET |

## Boot: bloqueio observado, não uma desculpa de escopo

O kernel original é uma imagem ARM64 em `boot.img`, com **42.897.920 bytes**;
o boot ramdisk tem **18.284.702 bytes**. SHA-256 do kernel armazenado:
`1ebce8efb8be90e29705bffeb1cbf4e9d954bab3104ec0a248282d4fcd7e25d5`.

Configuração recuperada:

```
CONFIG_ARCH_QCOM=y
CONFIG_ARM64_4K_PAGES=y
CONFIG_ANDROID_BINDER_IPC=y
CONFIG_ANDROID_BINDERFS=y
CONFIG_ANDROID_BINDER_DEVICES="binder,hwbinder,vndbinder"
CONFIG_SECURITY_SELINUX=y
CONFIG_KVM is not set
CONFIG_VIRTIO_BLK is not set
CONFIG_VIRTIO_NET is not set
CONFIG_VIRTIO_MMIO is not set
CONFIG_VIRTIO_PCI is not set
CONFIG_VIRTIO_CONSOLE is not set
CONFIG_SERIAL_AMBA_PL011 is not set
CONFIG_DRM_VIRTIO_GPU is not set
```

Esses dados não comprovam boot em QEMU. Indicam que a máquina `virt` padrão não
fornece, por si só, os dispositivos que esse kernel foi preparado para usar:
a combinação habitual de console PL011, transporte virtio e disco virtio não está
habilitada no kernel original. Não se deve prometer boot simplesmente anexando
`boot.img` e `system.img` a um emulador.

Possibilidades que exigem trabalho e validação, ainda não implementadas:

1. Portar/reconstruir um kernel guest com drivers virtuais e ABI compatível com os
   componentes originais; confirmar disponibilidade/proveniência das fontes e módulos.
2. Implementar dispositivos virtuais que atendam aos drivers originais necessários.
3. Combinar guest e bridges userspace, preservando contratos Binder/graphics/clock.

`CONFIG_KVM` no guest não determina acesso a KVM pelo APK host. Não existe evidência
de aceleração de virtualização acessível no X6873 sem privilégios. A emulação por
software e seu custo térmico/latência ainda não foram medidos.

## IPC: fatos novos

VINTF registra AIDL versão 2, serviço:
`oculus.internal.tracking.IMemoryBrokerService/default`.

A análise dos call sites `AIBinder_transact` recuperou:

| Interface | Método | Código | Flags |
| --- | --- | ---: | ---: |
| IMemoryBrokerService | getSharedMemoryFileDescriptor | 1 | 0 |
| IMemoryBrokerService | unregisterClient | 2 | 0 |
| IMemoryBrokerService | registerSharedMemory | 3 | 0 |
| IMemoryBrokerClient | onMemoryReallocation | 1 | 0 |

O parcelable `MemoryAllocation` é prefixado por tamanho e grava um
`ParcelFileDescriptor` não nulo, seguido de três `int32`. Não se adivinhou a
semântica dos três inteiros. FD Binder não é um inteiro serializado comum.

O broker original também possui verificações de permissões, AppOps e foco VR,
conforme strings e dependências observadas. Uma bridge não pode simplesmente
retornar sucesso para contornar essas dependências e ser considerada equivalente.

## O que falta antes de existir um port funcional

- Ambiente guest que execute kernel/framework/serviços originais com isolamento.
- Inicialização, linker namespaces, APEX, SELinux, identities e lifecycle compatíveis.
- Transporte original de memória compartilhada com layout/ownership/sincronização
  recuperados e testados, não apenas IDs de transação.
- Integração de compositor, GPU/buffers/fences/timing, display e óptica VRBox.
- Tracking de cabeça, mãos e passthrough ligados aos componentes originais.
- Validação de UI/apps originais e medições no telefone real.

Não houve boot, execução guest, modificação de firmware do Infinix ou entrega de
um APK Horizon. Reconstrução e análise estática não serão rotuladas como port.
