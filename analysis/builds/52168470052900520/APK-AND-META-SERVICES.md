# APK Cardboard e serviços Meta: estado e dependências reais

**Ainda não há APK funcional do Horizon OS, interface VR original ou conexão à Store.**
O objetivo continua sendo o software original, não uma interface substituta.
Este documento não afirma impossibilidade definitiva nem viabilidade/performance já comprovada.

## Trabalho executado nesta etapa

- Análise offline dos manifests originais de Store, DeviceAuthServer e AccountsCenterPWA.
- Disassembly completo de `.text` do serviço BootControl 1.2, implementação QTI e
  módulo legado bootctrl.anorak; dependências e configurações originais registradas.
- Novo DT guest coloca o controlador virtio efetivamente emulado sob `soc`, mantendo
  seus endereços/interrupts, para corresponder ao caminho dos scripts originais.
  **Não transforma virtio em UFS Qualcomm** nem implementa seus ioctls.
- Disco guest ganhou `misc` vazio de 4 MiB e `boot_a`/`boot_b`, ambos contendo a mesma
  imagem boot original verificada. Não há bootloader guest que implemente a seleção
  real desses slots; nenhum boot foi artificialmente marcado como bem-sucedido.
- Não houve modificação dos APKs, da assinatura de firmware, do init ou das políticas
  originais. Escritas permanecem em snapshot descartável. Sem rede ou acesso ao telefone.

Teste mais recente: [Actions 36675895578](https://github.com/AkunDiscoRemake/MetaPort-HorizonOSPort/actions/runs/36675895578),
código `31e9712`, relatório `16a336a`. Inspeção anterior: Actions 36675267147.

**Resultado:** os filesystems continuam montando e o segundo estágio continua
executando. **A adaptação não resolveu o BootControl:** o cliente ainda esperou
`android.hardware.boot@1.0::IBootControl/default` até o limite de 180 segundos.
A próxima investigação precisa capturar os erros internos do serviço (logd/logcat)
e verificar acesso a misc/slots e registro HIDL. Não atribuir a causa restante
exclusivamente a misc sem evidência adicional.

## BootControl: evidência estática

O RC original declara `vendor.boot-hal-1-2` com interfaces HIDL 1.0, 1.1 e 1.2.
A ausência da interface **AIDL** no VINTF, sozinha, não explica a falha: existe fallback
HIDL, e é esse fallback que também fica esperando no teste.

A implementação QTI SHA-256
`d7c64a4104b1c30bcb1a355929fba778e2977c517b1cfc5a0c1bd607f2ea4fc9` contém:

- `HIDL_FETCH_IBootControl` em `0x12db0`, chamada de `bootcontrol_init` em `0x12df8`;
- `bootcontrol_init` em `0x10a10`, chamada de `InitMiscVirtualAbMessageIfNeeded` em `0x10a8c`;
- acesso a GPT, misc, `/dev/block/bootdevice/by-name`, xbl/xblbak e UFS/SCSI;
- o RC `init.anorak.rc` espera `/dev/block/platform/soc/${ro.boot.bootdevice}` e
  cria `/dev/block/bootdevice` apontando para ele.

Isso orienta a adaptação, mas disassembly não prova sucesso de execução dessas funções.

## Componentes originais de conta e loja

| Componente | Identidade observada | Dependência relevante |
| --- | --- | --- |
| Store.apk | com.oculus.store, 313.0.0.4.153 | Permissões de IPC privado/multilayer do VrShell e serviços Oculus/Horizon |
| DeviceAuthServer.apk | com.oculus.deviceauthserver, 14 | sharedUserId android.uid.system; permissão horizonos.permission.OBTAIN_ROOT_AUTH_TOKEN |
| AccountsCenterPWA.apk | com.meta.AccountsCenter.pwa, 1.0.0.370722790 | Manifest inspecionado; fluxo de autenticação não executado |

Hashes:
- Store: `6fb15ceb6ab364224da5943a8aa43dfd0e117690f133bfa9dc64145bc6fb9e5d`;
- DeviceAuthServer: `5540a1be221b9e662f81273ebee693b1e1b81cf5dca361db7b4dcfdb495f31fc`;
- AccountsCenterPWA: `17c1702bd9b9e1964326ceeabacb71c618e8ba2aa276c563ac4caf481c4177c8`.

Esses manifests não fornecem tokens nem demonstram um protocolo de login funcional.
`OBTAIN_ROOT_AUTH_TOKEN` é o nome de uma permissão de autenticação do sistema original;
não é uma instrução para obter root no Infinix.

Copiar esses APKs para instalação comum no Android hospedeiro não fornece a UID de
sistema, os IPCs e os serviços esperados. Preservá-los dentro do guest mantém esse
objetivo arquitetural, mas o guest ainda não completou o boot.

## Servidores Meta

Nenhum servidor Meta foi contatado pelo guest. Nenhuma conta, token, compra,
atestação ou licença foi testada. Não existe evidência de aceitação **nem de recusa**
desse port pelos servidores. Autorização relatada para portar versões não prova
compatibilidade técnica ou aprovação de uma integração de serviços online.

Uma integração futura precisa de boot funcional, rede/TLS com validação de certificados,
relógio correto, componentes de conta e um fluxo legítimo aceito pela Meta. Permanece
necessário verificar login, catálogo, direitos de uso e download de forma separada.
Não forjar identidade provisionada/atestação, copiar credenciais de dispositivos,
burlar licenças ou tratar uma página web aberta como a Store original integrada.
Senhas e tokens não devem ser enviados ao chat, salvos no repositório ou nos relatórios.

## Antes de poder entregar o APK pedido

1. Resolver BootControl, dados/criptografia e demais dependências de inicialização.
2. Executar runtime/compositor e Home/System UI originais, com os adaptadores necessários.
3. Integrar ao processo Android não privilegiado o guest e seus backends reais.
4. Implementar saída estéreo, correção óptica/calibração Cardboard, entrada e ciclo
   de vida, validando latência/performance no X6873. Os backends atuais não são essa ponte.
5. Validar separadamente os serviços Meta legítimos. Seu funcionamento não pode ser
   prometido apenas porque kernel/init ou uma conexão HTTPS funcionam.

Não foi criado um APK vazio, launcher falso ou login simulado para substituir esses passos.
