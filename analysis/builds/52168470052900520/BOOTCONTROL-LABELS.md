# BootControl: rótulo SELinux incorreto confirmado; correção ainda não aplicada

**NOT PORTED YET. Não houve avanço para boot completo, Home, APK ou Store.**

## Experimentos executados

| Actions | Código | Observação |
| --- | --- | --- |
| 36712602106 | 71aed4e | Negação SELinux de acesso do HAL a vda3/misc registrada |
| 36713384014 | 47d5b75 | Regras originais extraídas; execução de logcat também negada pela política |
| 36714190455 | 9bd4697 | Tabela guest gerada, mas bind mount recusado; BootControl continua esperando |

Último relatório bruto: `guest-report.json`, publicado em `4375288`.
Esses testes são **instrumentados**, com `androidboot.init_rc` apontando para uma
configuração em metadata que importa os scripts originais. Não são idênticos ao
boot sem instrumentação. Nenhum init/binário HAL foi substituído.

## Evidência do bloqueio

```text
avc: denied { getattr } ... path="/dev/block/vda3"
scontext=u:r:hal_bootctl_default:s0
tcontext=u:object_r:vd_device:s0 tclass=blk_file permissive=0
```

vda3 é a partição misc do disco construído por `guest/storage.py`.
A política de rótulos original contém:

```text
/dev/block/platform/soc/1d84000.ufshc/by-name/misc u:object_r:misc_block_device:s0
```

A configuração da plataforma contém:

```text
/dev/block/vd[a-z][0-9]* u:object_r:vd_device:s0
```

O endereço/nome do controlador virtio não corresponde ao caminho literal original.
Os logs comprovam uma negação real ao HAL, não apenas uma hipótese de dependência.
Isso não prova que corrigir o rótulo resolva todos os demais problemas do BootControl.

## O que foi implementado e falhou no teste

`guest/labels.py` gera entradas exatas para vda1–vda7, associadas à ordem GPT criada,
usando exclusivamente os tipos já existentes da política original. Rejeita nomes
sem regra original ou com regras conflitantes. Não gera permissões `allow`.

O teste preservou o arquivo original como prefixo de uma tabela estendida no
filesystem metadata descartável. Tentou disponibilizá-la em early-init antes de
ueventd por bind mount, sem editar a partição vendor assinada. O resultado foi:

```text
mount none /metadata/vendor_file_contexts.metaport /vendor/etc/selinux/vendor_file_contexts bind
... failed: mount() failed: Permission denied
```

**As entradas geradas não foram aplicadas.** `storage.guest_label_overlay` no
relatório lista as entradas propostas; não é prova de rótulos efetivos.
A causa exata da recusa de mount não foi isolada apenas por essa mensagem.
O init também recebeu negação `relabelfrom` ao executar restorecon sobre o arquivo
experimental em metadata. A abordagem de sobreposição em runtime não está validada.

O logger adicional tampouco foi executado com sucesso: há negação explícita do init
sobre `logcat_exec`. Não foi usada política permissiva, domínio alternativo ou
serviço falso para contornar essa negação. O diagnóstico confirmado veio dos AVCs
no console do kernel, não de uma sessão de logcat funcional.

## Estado do código

- `guest/diagnostics.py`: configuração experimental explícita, imports originais,
  criação/readback dos arquivos em metadata. Não produz uma UI nem um init substituto.
- `guest/labels.py`: geração restrita de rótulos, não aplicação comprovada.
- `guest/inspect_services.py`: preserva regras relevantes e identidade dos arquivos
  originais; imagens seguem verificadas antes de inspeção.
- `guest/probe.py`: passa a separar negações do HAL/logger e falha de mount de sucesso.
- **O workflow voltou ao modo sem `--diagnostics` por padrão.** O experimento falho
  continua disponível explicitamente para pesquisa; não é apresentado como correção.
  Na revisão 0469727, a remoção do flag e os classificadores tinham somente teste
  local. Os ensaios posteriores de compatibilidade de nomes estão registrados em
  [BOOT-CONTROLLER-ALIAS.md](BOOT-CONTROLLER-ALIAS.md).

## Próxima decisão técnica

A adaptação dos rótulos precisa ocorrer por um mecanismo permitido durante a
preparação do guest, ou por uma imagem guest adaptada e identificada como tal — não
por uma sobreposição em runtime que a política rejeita. Uma imagem modificada exige
tratar sua própria integridade/assinatura e distinguir isso da assinatura original
Meta. Nenhum estado de Verified Boot Meta deve ser inventado.

Ainda faltam userdata/criptografia, TEE, módulos e interfaces físicas, gráficos,
compositor/runtime, integração APK e validação no Infinix. Nenhum servidor Meta foi
contatado, nenhuma conta foi utilizada e nenhum arquivo do telefone foi modificado.
