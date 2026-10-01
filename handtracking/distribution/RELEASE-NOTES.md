# MetaPort HandTracking — recuperação parcial, não APK

Subsistema independente de código/IA original, reutilizado pelo build nativo do
MetaPort. **A inferência Quest 3 no MediaTek ainda NÃO ESTÁ PORTADA.**

- `sources.zip`: fontes GPLv3 próprias, ferramentas da IA, componentes C++, testes,
  catálogo e relatórios de engenharia reversa; não contém pesos/binários Meta.
- `recovered.zip`: o conteúdo acima + os **25 recursos handtracking inventariados**
  no firmware Quest 3 52168470052900520: **21 arquivos de modelos e quatro assets**.
  Inclui também engine/service e dependências inspecionadas, totalizando **41
  originais verificados**; dez PTEZ também aparecem descomprimidos como PTE.
- Cada arquivo original e cada modelo descomprimido é comparado com SHA-256 pinado
  antes da publicação. Manifesto de todos os arquivos dentro do ZIP e checksum
  externo para o download.

Não é “toda a IA funcionando”, não é coleção comprovadamente completa de todas as
 otimizações e não é APK instalável. A enumeração dos 25 recursos é completa para
 o inventário dessa pasta/firmware, não para todas as dependências do Horizon OS.
Não há validação física no Infinix X6873. Backend Hexagon, ABI, câmeras/calibração
 e ligação ao renderer original continuam pendentes.

Código próprio GPL-3.0-only; componentes Meta/terceiros NÃO são relicenciados.
Veja THIRD-PARTY-NOTICE.md. O solicitante relata autorização, não verificada
independentemente; esta publicação não concede direitos sobre esses componentes.
