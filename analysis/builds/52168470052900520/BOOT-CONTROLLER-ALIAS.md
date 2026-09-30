# Compatibilidade de nomes do controlador de boot

## Escopo

Adaptação restrita no kernel público Meta fixado em
`8f32bdea05abf85dd10d6202963f7e9bdc55c717`, que não é a fonte exata da OTA.
O controlador continua sendo **virtio MMIO**, com recursos reais em `0x0a000000`
e tamanho `0x200`. Não há implementação de UFS, SCSI, Qualcomm TrustZone ou
atestado de identidade Meta nesta alteração.

`guest/kernel/boot-controller-alias.patch` dá ao dispositivo de plataforma o nome
`1d84000.ufshc` somente quando todas estas condições são satisfeitas:

- máquina DT compatível com `metaport,virt`;
- nó compatível com `virtio,mmio`, marcado `metaport,boot-controller-alias`;
- filho direto de `soc`, sendo `soc` filho direto da raiz;
- endereço/tamanho reais iguais aos valores acima;
- ausência de um nome explícito fornecido pelo chamador.

O DT mantém `linux,dummy-virt`, o protocolo e os recursos originais. Os parâmetros
`boot_devices`/`bootdevice` usam o nome adaptado. O objetivo é permitir que as regras
originais do ueventd atribuam os papéis das partições pelo caminho esperado. Não
foram adicionadas permissões SELinux nem alteradas as imagens verificadas, o initrd
ou a política original. O experimento de overlay de contextos permanece desligado.
O build verifica SHA-256 do arquivo-fonte antes de aplicar o patch sem fuzz; a chave
de cache inclui os arquivos do diretório do kernel.

## Ensaios medidos

### 36716801539 — fonte faac714 — regressão

O kernel compilou, mas não ativou o alias. A comparação de `full_name` com `/soc`
não era adequada à representação do nó usada pelo kernel. Com o parâmetro de boot
já apontando para o novo nome, o init não encontrou `/dev/block/by-name/super` e
reiniciou, antes do segundo estágio. **Não foi um avanço.**

### 36719412359 — fonte e5a68f8 — avanço parcial

A checagem passou a usar `of_node_name_eq` e a profundidade na árvore. O kernel
registrou a ativação do alias e o init original voltou a executar o segundo estágio.

- Kernel SHA-256: `321ce9b7db1ae968bedd0bbad7dffb2957aface69a95637715b512d903be3265`.
- Initrd inalterado: `dc0ee2795c81bd0b426a791b9ec0544943900af95f351edbdee9124d24bd5118`.
- Serviço `vendor.boot-hal-1-2` iniciado em aproximadamente 67 s.
- O boot chegou a ações de `post-fs-data` e tentativas de iniciar o Zygote.
- Em 142,464656 s, o cliente original `update_verifier` registrou
  `Using HIDL version 1.2 of IBootControl`.
- Continuam negações SELinux de **read/write no disco inteiro `vda`**, com tipo
  `vd_device`. Isso não é a negação anterior de getattr em `vda3`/misc.
- `/data` continua indisponível para gravação; há falhas/reinícios de Zygote,
  keystore e outros serviços. Não há userdata provisionada nem TEE adaptado.
- Supervisão encerrou a execução em 180 s. Sem rede, sem KVM e sem alteração do telefone.

A obtenção do HAL por um cliente é evidência mais forte do que apenas a existência
do processo, mas **não valida todas as operações de slots, GPT, merge ou atualização**.
Também não há leitura direta do contexto efetivo de misc neste ensaio: a evidência
é comportamental, não um `ls -Z` bem-sucedido.

## Correção do relatório

O classificador anterior chamava qualquer negação hal_bootctl→vd_device de negação
em misc, incluindo o disco inteiro. A revisão `6b68a9e` separa explicitamente `vda3`
e `vda`, registra o uso HIDL pelo cliente e distingue tentativa de iniciar Zygote de
boot completo. O booleano `bootcontrol_misc_label_denial_observed` do relatório da
execução 36719412359 é, portanto, um falso positivo de classificação — não uma prova
de que a negação anterior continuou. Um teste de regressão cobre essa distinção.

## Repetição 36721399779 — fonte 6b68a9e

O relatório atual foi publicado em `d4c8104`; o relatório do ensaio anterior está
preservado no histórico, em `26b1ba7`. A repetição reutilizou exatamente o mesmo
kernel SHA-256, sem configuração diagnóstica. Observou:

- alias ativado, segundo estágio e `post-fs-data`;
- nenhuma negação classificada em `vda3`/misc no console capturado;
- negação real no disco inteiro `vda`, às 96,69 s;
- `checkpoint restoreCheckpoint` retornando que `userdata` não existe;
- `mount_all --late` encerrando após 41,422 s e pulando userdata;
- `/data` somente leitura, sem boot completo.

Neste ensaio não apareceram o marcador do cliente HIDL 1.2 nem tentativa de iniciar
Zygote dentro da janela de 180 s. Os respectivos flags permanecem **false**: o
resultado anterior não é copiado para o novo relatório. Os marcos mais avançados
estão comprovados somente no ensaio 36719412359, não em todos os boots. A ausência
nessa janela não identifica, por si só, sua causa.

Validação local: 30 testes guest (29 passaram, 1 skip opcional LZ4) e 53 testes
existentes (52 passaram, 1 skip opcional). As três execuções Actions terminaram,
mas somente os eventos descritos, não o status verde, são evidência de progresso.

## Limites

**NOT PORTED YET:** sistema Horizon completo, Home/compositor/runtime XR, interfaces
físicas, armazenamento criptografado/TEE, APK executável no Infinix e Meta Store.
Nenhuma conta, token, compra, licença ou resposta de servidor Meta foi testada.
Um workflow verde não significa um sistema funcional.
