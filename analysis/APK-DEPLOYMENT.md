# Alvo: APK não privilegiado no Infinix X6873

## Restrições confirmadas pelo solicitante

GT30 Pro, X6873, XOS 16.2; bootloader bloqueado. Sem desbloqueio, root, flash,
substituição do sistema ou alteração de políticas SELinux. A versão Android/API,
ABI e capacidades efetivas ainda precisam ser medidas. XOS não é número de API.
Perfil: `devices/infinix-x6873.json`. Não há promessa sobre cobertura de garantia.

## Execução original dentro de um APK

A emulação de hardware executando componentes originais é diferente de uma UI
simulada e pode ser investigada. Porém, não existe ainda um emulador integrado aqui.
Disassembly é uma técnica de análise, não um mecanismo que automaticamente converte
um firmware em APK ou remove suas dependências.

Rotas a avaliar **após** identificação dos binários:

1. Componentes userspace originais da mesma ISA, com bridges de ABI e serviços.
   Mesma ISA não garante compatibilidade de linker, libc, Binder ou privilégios.
2. Emulação de sistema completo em userspace: kernel e serviços guest, dispositivos
   virtuais e bridges para as APIs permitidas ao APK. Não presumir acesso a KVM,
   virtualização acelerada, GPU passthrough ou drivers do headset.
3. Combinação das duas somente quando os contratos originais justificarem.

Nenhuma rota está selecionada nem tem boot comprovado. Um guest privilegiado não
concede privilégios ao APK host. Câmera, sensores e áudio continuam sujeitos a
permissões e lifecycle Android. A integração gráfica teria de traduzir interfaces
originais para recursos acessíveis ao host; framebuffer via cópia de CPU não deve
ser apresentado como compositor VR de baixa latência.

## Pesquisa inicial de artefatos

Não foi localizada nesta pesquisa uma imagem cuja build estável v2.4/v2.7 pudesse
ser verificada e aceita. Nenhum firmware foi baixado, extraído ou executado.

As notas oficiais encontradas apresentam uma entrada de v2.7 explicitamente como
**Public Test Channel**, semana de 27 de julho de 2026. Essa entrada não comprova
um artefato estável e não autoriza aceitar PTC, excluído pelo escopo original.
[1](https://www.meta.com/en-gb/help/quest/172903867975450/)

A busca não é exaustiva. Não confundir ausência de artefato aceito com inexistência
das versões. Extensões ISO/IMG não comprovam conteúdo, versão, integridade ou se a
imagem contém um sistema completo. Um OTA incremental pode exigir uma base; se a
base for de versão fora do escopo, não a usar para reconstrução. Solicitar pacote
completo autorizado. Não usar download automático de “latest”.

## Preflight opcional sem modificar o sistema

Com Android Platform Tools no computador e depuração USB já autorizada:

```sh
mkdir -p local-analysis/device
python3 tools/device_probe.py > local-analysis/device/preflight.json
```

Se houver vários aparelhos, selecionar com `--serial`. A ferramenta só consulta
uma lista restrita de propriedades e features; não instala APK, não reinicia,
não executa root/fastboot e não coleta serial no relatório. Saída zero é necessária
para aceitar o JSON. Acesso via ADB não comprova acesso do futuro APK às mesmas APIs.
Desativar depuração USB após a coleta, se não for mais necessária.

Features declaradas não são benchmarks, certificação ARCore ou teste funcional.
Um teste futuro dentro de APK deve medir câmera, sensores, disponibilidade ARCore,
extensões GPU, modos de display, timestamps e comportamento térmico.

## Otimização e proteção do aparelho

Somente otimizar caminhos reais medidos: frame time CPU/GPU, latência de tracking,
cópias de buffers, sincronização e consumo térmico. Não prometer FPS antes disso.
Evitar tradução de CPU quando a execução nativa for realmente compatível; reduzir
cópias usando buffers compartilháveis quando suportados; testar Vulkan/GLES no
hardware antes de escolher. Resolução dinâmica não corrige incompatibilidade de ABI.

Para o painel com burn-in relatado: não iniciar testes longos, brilho máximo, telas
estáticas ou wake locks permanentes. Um APK não repara burn-in. Testes futuros devem
ser curtos, canceláveis, pausar em background e respeitar alertas térmicos; não
alterar controles térmicos do fabricante.

**Resultado atual: NOT PORTED YET. Nenhum teste físico ou boot guest realizado.**

## Aquisição via GitHub Actions

Workflow `.github/workflows/fetch-firmware.yml`: tenta baixar exclusivamente o
candidato `q3_52168470052900520.zip` e compara seu SHA-256 ao publicado no catálogo.
Não extrai nem executa conteúdo. Falhas de HTTP, TLS ou hash impedem o upload.
O limite de download é 10 GiB; o artifact tem retenção de um dia e não entra no Git.
Consome a cota de armazenamento/execução de Actions; o download pode falhar também
nessa rede. Em repositório público, tratar artifacts como publicamente acessíveis:
não colocar segredos nem outros arquivos nesse workflow.

O primeiro disparo ocorre ao publicar o workflow na branch da sessão. Para repetir,
abrir Actions → Fetch firmware candidate → execução → Re-run all jobs. O botão
manual de workflow_dispatch pode exigir que o workflow exista na branch padrão;
não é necessário mudar de branch para repetir uma execução existente.

Mesmo após hash válido, permanece pendente confirmar versão estável v2.4 e se o
pacote é completo. Não iniciar RE dos componentes antes dessa revisão de escopo.
