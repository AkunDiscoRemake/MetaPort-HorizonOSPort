# UI/UX original — continuação do MetaPort

Não contém uma UI substituta. O workflow `ui-decompilation.yml` extrai os APKs
originais VrShell, MetaSystemUI, SystemUX, SettingsPanelApp e LibraryPanelApp da partição verificada e executa JADX 1.5.6 pinado.
Agora também decodifica recursos (antes `--no-res`) e registra separadamente:

- candidatos de passthrough e composição de superfícies;
- painéis/navegação e animações/transições;
- entrada de mãos/controles e serviços privilegiados;
- inventário limitado de XMLs com hashes, contextos de animação e erros do decompilador.

As bibliotecas ARM64 embarcadas também têm seus metadados ELF inspecionados,
com limites de tamanho/quantidade. Isso não equivale a decompilar suas funções.

`evidence.py` é um índice de candidatos com contexto e limites explícitos, **não
um grafo de chamadas resolvido**, nem prova de ABI utilizável. Relatórios ficam em
`analysis/builds/52168470052900520/ui-decompilation.json`, campo `ux_evidence`.
Contagens incluem todo o texto analisado; amostras truncadas são sinalizadas.
JADX reconstrói Java; não recupera o código-fonte original exato. Código nativo de
composição continua exigindo análise ELF/Ghidra separada.

## Próximas ligações que precisam de evidência

1. Identificar callbacks de apresentação, vida útil das superfícies e thread GL.
2. Resolver JNI/Binder e dependências de assinatura/permissões de sistema.
3. Adaptar a saída original para `EglOutput` sem criar UI clone.
4. Conectar o fundo de câmera ao compositor original, preservando a ordem das
   camadas e a política original de interação/oclusão onde recuperável.
5. Conectar inferência real ao módulo `handtracking`, sem fabricar poses.

O novo fundo ARCore usa câmera física/OES, mas **a conexão ao compositor Horizon
não está portada**. Não existe medição de FPS/latência/consumo no Infinix ainda.
Não se prometem todos os recursos do firmware dentro de APK sem privilégios.
