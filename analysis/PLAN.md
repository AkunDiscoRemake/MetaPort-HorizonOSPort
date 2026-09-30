# Plano de portabilidade baseado em evidências

> Atualização: a restrição de versões/canal abaixo foi substituída por [SCOPE.md](SCOPE.md). Resultados antigos permanecem históricos.

## Gate de escopo

Antes de extrair ou analisar componentes, confrontar a versão declarada com
metadados de build e registros de aquisição. Registrar hashes, origem, identificação
completa, método de verificação e responsável pela revisão em armazenamento local.
Em caso de inconsistência ou versão desconhecida, interromper a análise. O inventário
não substitui essa revisão. Não comparar com nenhuma versão além de v2.4 ↔ v2.7.

## Estado por subsistema

Todos os itens abaixo estão **NOT PORTED YET**. Os backends são hipóteses de
investigação, não interfaces identificadas nem implementações existentes.

| Destino planejado | Evidência necessária | Adaptação a investigar |
| --- | --- | --- |
| horizon/framework | Framework, ABI, permissões, dependências | Bridges Android somente onde necessárias |
| horizon/runtime | Executáveis, linker, dependências de processo | NDK/JNI e implantação privilegiada quando exigida |
| horizon/services | Serviços, IPC, identidade e ordem de inicialização | Binder, políticas e ciclo de vida |
| horizon/systemui | Componentes reais, recursos, serviços consumidos | Integração das superfícies originais |
| horizon/compositor | Contratos de layers, buffers, fences, timing | Vulkan/EGL, Android display |
| horizon/xr | Runtime, loader, extensões e contratos OpenXR | Spaces, actions, swapchains e sessões reais |
| horizon/tracking | ABI de pose, tempo, coordenadas, confiança | ARCore + sensores; perda explícita de tracking |
| horizon/handtracking | Estruturas, joints, confiança e aquisição | Câmera + backend CV/ML compatível |
| horizon/passthrough | Aquisição, composição, calibração e oclusão | Camera2, sincronização e geometria |
| horizon/input | Eventos, controles, foco e permissões | Dispositivos Android compatíveis |
| horizon/audio | Grafo de áudio, latência e espacialização | Áudio Android/native |
| horizon/applications | Pacotes, assinatura, privilégios e lifecycle | Compatibilidade real, sem prometer apps universais |
| boot / drivers | Partições, kernel, HALs e cadeia de inicialização | Avaliar imagem específica do smartphone |
| storage / networking | Serviços, isolamento, protocolos e acesso | Backends Android respeitando permissões |
| telemetry / local services | Contratos, consentimento e dependências | Preservar privacidade; não fabricar respostas remotas |
| vrbox | Perfil óptico e geometria física | Stereo, IPD, FOV, distorção, calibração |

Não criar stubs com retorno de sucesso. Não definir uma ABI “Horizon” fictícia.
Criar as árvores de implementação `horizon/`, `port/`, `vrbox/` e `native/` quando
houver contratos reais identificados para implementar, não como sinal de conclusão.

## Sequência e critérios de aceite

1. **Aquisição e identificação:** evidência de versão revisada, inventário estável.
2. **Análise estática isolada:** formatos, ABI/ISA, bibliotecas importadas, serviços,
   recursos e dependências de hardware. Não executar binários desconhecidos no host.
3. **Contratos observados:** para cada interface registrar componente e hash,
   evidência/localização, assinatura, ownership, threading, clocks, unidades,
   coordenadas, erros e requisitos de privilégio. Distinguir inferência de observação.
4. **Decisão de implantação:** confrontar dependências com hardware/Android alvo.
   Documentar componentes que exigem ROM modificada ou não têm backend equivalente.
5. **Primeiro caminho vertical real:** inicializar um componente original com seu
   backend mínimo e demonstrar chamadas reais; não substituir o componente por demo.
6. **Integração:** runtime, compositor, System UI e aplicações reais; só depois
   validar tracking, mãos, passthrough e sessões XR de ponta a ponta.
7. **Validação física:** comparar comportamento com referência da mesma versão;
   registrar dispositivo, build, logs, limites e falhas. Testes de ferramentas não
   constituem validação de compatibilidade Horizon OS.

### Critérios obrigatórios dos adapters

- Tracking: transformação explícita de coordenadas e timestamps, origem/recenter,
  floor/planes/anchors onde suportados, estados de perda e confiança não fabricada.
- Câmera: permissões, arbitragem ARCore/Camera2, clocks, calibração e lifecycle.
  Não assumir que ARCore e hand tracking podem abrir simultaneamente a mesma câmera.
- Display: superfícies reais, fences, predicted display time, left/right eye,
  resolução, refresh e parâmetros ópticos medidos; respeitar lifecycle Android.
- XR: apenas extensões realmente implementadas; erros honestos para recursos ausentes.
- Performance: medir frame time CPU/GPU, latência, frames perdidos e térmica antes
  de ativar multiview, resolução dinâmica ou fallback Vulkan/OpenGL ES.
- Segurança: preservar isolamento, permissões e consentimento de câmera/microfone;
  não contornar assinaturas ou fabricar autenticação para alegar compatibilidade.

## Registro de adaptações

Cada adaptação deve documentar: comportamento original observado → incompatibilidade
física/plataforma → adapter mínimo → testes de equivalência → diferenças restantes.
Não prometer o mesmo comportamento observável quando faltarem dados de sensor ou
privilégios indispensáveis. Registrar a limitação e manter **NOT PORTED YET** até
haver implementação e evidência de integração.
