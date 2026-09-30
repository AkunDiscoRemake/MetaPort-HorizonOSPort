# Userdata descartável: bloco presente, criptografia/boot ainda bloqueados

**NOT PORTED YET. Nenhum telefone foi acessado ou modificado.**

Ensaio [36761552459](https://github.com/AkunDiscoRemake/MetaPort-HorizonOSPort/actions/runs/36761552459),
source `72dcaf3`, com kernel experimental em cache, QEMU TCG e limite de 180 s.
A evidência completa está em `guest-report.json`.

## Implementação

`guest/storage.py --userdata-mib 1024` acrescenta ao GPT uma partição `userdata`
de 1 GiB, inicialmente zerada por arquivo sparse novo, depois das partições
existentes. Seus índices e offsets anteriores permanecem iguais. O parâmetro é
opcional e limitado; sem ele, o builder preserva o layout anterior.

Não foi criado ext4 sem criptografia para substituir a política original.
O `fs_mgr`/`vold` original é responsável por reconhecer, formatar e provisionar
esse armazenamento. As escritas do guest continuam restritas ao snapshot
QEMU descartável. Nenhuma chave ou dado pessoal de headset/telefone foi copiado.

Os bytes das partições originais, SELinux e a configuração AVB não foram
alterados. A existência do bloco não fornece KeyMint/Keymaster, TEE, chaves
wrapped ou serviços Android funcionais.

## O que mudou de fato

No ensaio anterior, o cliente checkpoint falhava com `No such file or directory`
ao abrir `userdata`. Neste ensaio foram observados:

- `checkpoint restoreCheckpoint .../userdata`: retorno `22: No magic`;
- `Invalid ext4 superblock on .../userdata`;
- chamada original `vdc cryptfs encryptFstab .../userdata /data true ext4`;
- espera repetida por `android.system.keystore2.IKeystoreService/default`, não
  encontrado pelo servicemanager, até o timeout do ensaio.

Os dois primeiros resultados são compatíveis com o bloco novo ainda sem
filesystem; não indicam montagem bem-sucedida. A chamada de criptografia é uma
**tentativa**, não confirmação de chaves criadas ou `/data` montado.

O fstab original capturado requer, entre outras opções:

```
fileencryption=aes-256-xts:aes-256-cts:v2+inlinecrypt_optimized+wrappedkey_v0
keydirectory=/metadata/vold/metadata_encryption
metadata_encryption=aes-256-xts:wrappedkey_v0
```

Não se deve retirar essas opções ou criar um serviço que anuncie sucesso falso
para encobrir a falta do backend. A causa completa da indisponibilidade do
Keystore ainda exige inspeção do seu startup, dependências e backend de chaves;
a mensagem de espera, isoladamente, não identifica a causa raiz.

## Limites e comparação de estágios

- Segundo estágio do init: observado.
- `post-fs-data` neste ensaio: **não observado**.
- Tentativa de iniciar Zygote neste ensaio: **não observada**.
- `boot_completed`, UI original e APK: **não obtidos**.
- Kernel panic: não observado; ensaio encerrado pelo limite de tempo.

Ensaios anteriores sem userdata chegaram a `post-fs-data` e tentaram iniciar
Zygote com dados indisponíveis. Portanto, este ensaio **não foi um avanço na
etapa final de boot**: ele forneceu o bloco faltante e passou a exercitar um
caminho de provisionamento que ficou esperando o Keystore. Isso precisa ser
resolvido com uma implementação real das dependências, não por trocar o status
para sucesso.
