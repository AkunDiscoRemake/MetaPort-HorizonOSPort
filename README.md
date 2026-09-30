# MetaPort — Horizon OS → Android + VRBox

**Estado: NOT PORTED YET. Não há um Horizon OS executável neste repositório.**

O objetivo é portar componentes reais das versões **v2.4 e v2.7**, preservando
arquitetura e comportamento onde tecnicamente possível. Nenhuma outra versão está
no escopo, inclusive builds de versão desconhecida, betas e builds internas.
A autorização informada pelo solicitante refere-se exclusivamente a essas versões;
ela não identifica a versão de um arquivo nem estabelece direitos de redistribuição.

O checkout inicial continha somente um README. Não foram fornecidos fontes,
imagens, binários, interfaces extraídas ou hardware alvo. Não foram realizadas
engenharia reversa, integração Android ou validação em dispositivo. Não existem
launcher, UI substituta, compositor de demonstração ou poses sintéticas.

## O que existe

- Inventário local de arquivos com tamanho e SHA-256, sem executar os componentes.
- Restrição do parâmetro de versão a `v2.4` ou `v2.7`.
- Referência de proveniência obrigatória e estado de versão `UNVERIFIED` explícito.
- Rejeição de diretório vazio, symlinks e arquivos especiais.
- Testes automatizados e plano de investigação em [analysis/PLAN.md](analysis/PLAN.md).

Isso é infraestrutura de análise, **não implementação do sistema portado**.

## Inventário local

Requer Python 3.10+ em Linux; não requer dependências externas.
Use somente uma cópia estável, local e previamente identificada como pertencente
às versões autorizadas. Não a modifique durante o inventário; a ferramenta não é
uma sandbox para árvores alteradas por terceiros nem um verificador de autenticidade.

```sh
mkdir -p artifacts/v2.4 local-analysis/v2.4
# Colocar os artefatos autorizados em artifacts/v2.4 antes de executar.
python3 tools/inventory.py \
  --version v2.4 \
  --artifacts artifacts/v2.4 \
  --provenance 'Referência ao registro local de aquisição e identificação da build' \
  > local-analysis/v2.4/inventory.json
python3 -m unittest discover -s tests -v
```

Para v2.7, usar diretórios e argumento correspondentes. A saída deve ficar **fora**
da árvore inventariada. Erros resultam em código de saída não zero; não consumir
um relatório sem verificar o resultado do comando. A ferramenta não extrai imagens,
não baixa firmware e não confirma que a declaração de versão é verdadeira. Hashes
identificam bytes, não autorização ou autenticidade. Não processar artefatos de
versão desconhecida com uma etiqueta autorizada para contornar o escopo.

`artifacts/` e `local-analysis/` ficam fora do Git. Não adicionar firmware, chaves,
credenciais, dados pessoais ou assets proprietários ao histórico por padrão.

## Insumos necessários para iniciar o port

1. Artefatos reais v2.4 e/ou v2.7, identificação exata da build e evidência de origem.
2. Smartphone alvo: modelo, SoC/GPU, ABI, Android, câmeras, sensores, suporte ARCore.
3. Modalidade de implantação: APK não privilegiado, instalação privilegiada ou
   imagem Android modificada; disponibilidade de bootloader desbloqueável e root.
4. Modelo óptico do VRBox/Cardboard e disponibilidade física das câmeras durante uso.
5. Dispositivo original ou registros de referência para validação comportamental.

Um APK comum não pode substituir boot, HALs e serviços privilegiados do Android.
A viabilidade e o alcance de cada modalidade dependem das dependências reais do OS.
ARCore não garante equivalência com tracking de headset, e câmeras de smartphone
não garantem cobertura, sincronização, profundidade ou latência equivalentes.
Recursos indisponíveis devem ser reportados como indisponíveis, nunca inventados.

## Alvo definido

**Infinix GT30 Pro X6873 / XOS 16.2**, conforme informado pelo usuário. Implantação
exclusivamente em **APK comum**, sem root, flash ou desbloqueio do bootloader.
Ver [decisão de implantação e pesquisa de artefatos](analysis/APK-DEPLOYMENT.md).
Emulação de componentes originais será avaliada; não há emulador implementado.

`tools/device_probe.py` fornece uma coleta ADB opcional, somente leitura, para
preflight do aparelho. Não é o APK MetaPort e não comprova compatibilidade XR.

## Inspeção real do pacote candidato

O workflow já inspecionou o OTA no runner: manifesto FULL, 29 partições, cerca de
3,74 GB de tamanhos declarados e nenhuma dependência de imagem-base observada.
Ver [resultados e limites](analysis/v2.4/FINDINGS.md). Ainda não há confirmação do
canal estável, imagens reconstruídas, disassembly de componentes ou APK funcional.
A ferramenta de manifesto e a suíte de 24 testes são código executado, não um port.
