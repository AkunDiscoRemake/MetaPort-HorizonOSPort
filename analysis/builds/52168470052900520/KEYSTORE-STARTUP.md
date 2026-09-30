# Inicialização original de Keystore/KeyMint — diagnóstico, não substituição

**NOT PORTED YET.** Esta investigação não implementa um KeyMint fictício, não
fornece chaves falsas, não desativa criptografia/SELinux e não modifica o telefone.
Os testes rodam no guest descartável, sem rede e sem dados pessoais.

## Contratos recuperados e ligados a hashes

`guest/security_contract.py` verifica tamanho e SHA-256 das imagens system/vendor
contra a reconstrução da OTA fixa. Extrai dez configurações e doze ELF selecionados,
com hashes, dependências, amostras de símbolos/strings e declarações de init.
O parser de init registra texto e blocos: **não executa comandos, não resolve
imports/propriedades e não implementa toda a gramática de init**.

O resultado está em `guest-report.json.security_contract`, incluindo:

- Keystore2: `/system/bin/keystore2 /data/misc/keystore`, classe `early_hal`,
  usuário `keystore`, grupos `keystore readproc log`.
- `vendor.keymint-qti`: iniciado por ação `on init` e pertencente a `early_hal`.
- `vendor.qseecomd` e `qseecom-service`: possuem ações explícitas `on init`.
- VINTF declara `android.system.keystore2` AIDL v3, instância `default`.
- O manifesto vendor declara KeyMint, SharedSecret, SecureClock e
  RemotelyProvisionedComponent. Declaração **não comprova registro Binder**.
- `libqtikeymint.so` depende de `libkeymasterdeviceutils.so`, entre outras libs;
  esta depende de `libQSEEComAPI.so`. Há referência estática a `/dev/qseecom`.
  Isso não prova que um erro específico desse dispositivo causou a falha observada.

## Primeiro ensaio: não era simplesmente falta de `start`

Run [36768832018](https://github.com/AkunDiscoRemake/MetaPort-HorizonOSPort/actions/runs/36768832018),
source `46eb1b4`, registrou:

- 53 s: init inicia KeyMint/QSEE, atribuindo PIDs.
- 83 s: init inicia Keystore2 e atribui PID 252.
- 88 s: chamada de `vdc cryptfs encryptFstab .../userdata /data true ext4`.
- depois: espera pelo serviço `android.system.keystore2.IKeystoreService/default`.
- 91 s: AVC nega `ptrace` de `crash_dump64` para o domínio `keystore`.

A negação é da **coleta de diagnóstico**, não prova de que o SELinux impediu a
inicialização do próprio Keystore. Tampouco identifica a causa que levou à tentativa
de coleta. O estado do serviço não deve ser inferido apenas pelo texto de espera.

Foram acrescentadas amostras deduplicadas de eventos de segurança: mensagens
repetidas não eliminam do relatório os erros de startup anteriores ao trecho final
do console. Limites de tamanho e truncamento são explícitos.

## Rastreamento sem liberar ptrace

`guest/probe.py --trace-signals` pede ao kernel já usado no guest os eventos
`signal:signal_generate` e `sched:sched_process_exit`, via `tp_printk`. A seleção
registra metadados de sinais/processos, não dumps de memória ou conteúdo de chaves.
O comando mantém SELinux, AVB, falta de rede e limites de console/tempo.

Uma amostra separada de eventos correlacionados por nome/PID de serviço preserva
falhas tardias mesmo se eventos genéricos de outros processos encherem a amostra.
Gerar um sinal, isoladamente, não comprova sua entrega nem a causa fatal.

### Por que o primeiro trace não cobriu o Keystore

Run [36770339459](https://github.com/AkunDiscoRemake/MetaPort-HorizonOSPort/actions/runs/36770339459),
source `81206a7`, confirmou suporte do kernel e 110 eventos, mas o último publicado
no console era de aproximadamente 46 s. Keystore2 só foi iniciado aos 75 s.
**Zero eventos de Keystore nessa captura não significa ausência de falha.**

A configuração original `init.anorak.rc`, linha 135, escreve:

```
write /proc/sys/kernel/printk "6 6 1 7"
```

Ela coloca tanto o nível de console quanto o nível padrão de mensagem em 6.
No kernel público fixado, `output_printk()` usa `printk("%s", ...)`, sem prioridade
explícita. `suppress_message_printing()` filtra mensagens cujo nível é maior ou
igual ao nível de console. Portanto, essa configuração explica por que a captura
inicial perde a visibilidade do trace depois do ajuste original de printk.

A opção diagnóstica agora inclui `ignore_loglevel`, verificada no código do kernel
fixado. Isso altera **somente a visibilidade do console do guest**; não concede
permissões ao Keystore, não remove a política original nem muda a criptografia.
O teste com essa correção ainda precisa ser confrontado com seu relatório final.

## Publicação dos resultados

O run intermediário 36769961408 teve falha na etapa de publicação. O workflow
antigo não sincronizava a branch antes do push do relatório, embora commits de
desenvolvimento possam avançá-la durante o ensaio. O publisher foi alterado para
pull/rebase e até três tentativas de push normal, **sem force-push**. Conflitos de
conteúdo interrompem a publicação; não se escolhe silenciosamente um relatório.

## Limites atuais

Ainda não há `/data` montado com criptografia validada, registro Keystore confirmado,
`boot_completed` ou APK Horizon funcional. As dependências originais de segurança
ainda não foram adaptadas ao telefone. Strings de ELF, serviços iniciados e um
workflow verde não demonstram que essas dependências funcionem.
