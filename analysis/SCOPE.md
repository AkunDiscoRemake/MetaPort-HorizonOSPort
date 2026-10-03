# Escopo vigente

O solicitante informou nova autorização para **todas as versões do Horizon OS**.
Isso substitui o limite anterior v2.4/v2.7, incluindo a restrição de canal de build.
A autorização é registrada como declaração do solicitante, não verificada
independentemente por este projeto. Não se deduz direito de redistribuição pública.

Pode-se continuar a análise da build `52168470052900520` mesmo sem resolver o nome
comercial/canal. Essa incerteza de identificação continua explícita, mas não bloqueia
mais a extração ou o disassembly dentro do escopo declarado.

`SCOPE.json` registra a política. Relatórios e notas históricas que mencionam a
restrição antiga descrevem o estado daquela etapa e não se sobrepõem a este arquivo.
Não coletar outras versões sem necessidade: este trabalho continua focado no pacote
fixado por SHA-256 que já foi adquirido. Ferramentas não devem selecionar “latest”.

Permanecem: APK não privilegiado, bootloader bloqueado, sem root/flash no Infinix,
sem UI falsa, sem execução de firmware não confiável no host e sem promessas de boot.
Binários/imagens extraídos permanecem temporários e fora do Git; publicar apenas
relatórios técnicos mínimos. Não colocar pacotes completos ou assets extraídos em
novos artifacts públicos por padrão. Artifacts anteriores expiram conforme retenção.
