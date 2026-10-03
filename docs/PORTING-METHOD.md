# Como avançar para um port original, não uma demonstração

## Ferramentas já usadas e o que seus resultados significam

- **JADX:** reconstrução de Java/recursos dos APKs originais, com erros e arquivos
  omitidos registrados. Isso não produz automaticamente um projeto compilável.
- **Ghidra / disassembly ELF:** examinar JNI, ABI, chamadas, dados e instruções dos
  serviços/runtime. Tipos inferidos pelo decompilador precisam de confirmação.
- **QEMU user-mode ARM64:** os testes nativos de redução, packing e mapeamento FMQ
  já estão no workflow `build-adapters.yml`. Passar nesses testes não executa a IA.
- **QEMU system/TCG:** pesquisa de boot com init/partições originais e kernel
  adaptado, documentada em `guest/README.md`. Ainda não é um Horizon completo
  inicializado. Não requer flash nem desbloqueio do telefone.

Emulação de CPU não implementa automaticamente GPU, câmeras, calibração, serviços
Binder/HAL ou transporte Hexagon/FastRPC. QEMU não deve ser apresentado como atalho
que dará desempenho VR em todos os celulares. Só medições podem decidir onde usar
emulação; adaptadores nativos são preferíveis quando preservam o contrato original.

## Ordem técnica para o primeiro APK real

1. Escolher uma rota mínima **original** de apresentação: entrada do VrShell,
   chamadas JNI, criação de surface/contexto, ligação aos serviços usados nesse
   caminho. Demonstrar cada dependência; não carregar DEX às cegas e chamar crash
   ou tela vazia de port.
2. Recuperar tipos, propriedade de memória, sincronização, callbacks e política de
   threads. Validar pontes isoladamente antes de conectar câmera e compositor.
3. Ligar essa rota original à saída Android e a ARCore 6DoF/depth/passthrough como
   adaptação de hardware explícita. Não substituir UI/configurações por mockups.
4. Executar inferência original de mãos num backend compatível. Recuperar dados
   delegados, pré/pós-processamento e entradas reais; comparar resultados numéricos.
   Ter arquivos `.ptl/.ptez` e helpers SIMD não satisfaz esse critério.
5. Validar a experiência original no aparelho: inicialização, renderização, input,
   recuperação de tracking, lifecycle e erro de permissão sem poses inventadas.
6. Expandir funções de configurações e serviços, registrando as que exigem
   privilégios inacessíveis ao APK comum. Não desenhar um botão que não funciona.
7. Integrar clientes cloud apenas com acesso autorizado e autenticação/entitlement
   reais. Servidores e políticas Meta não podem ser extraídos da OTA.

A descoberta de um bloqueio pode exigir mudar a arquitetura; esta ordem não é
promessa de que todo o firmware seja portável sob as restrições atuais.

## Resultados mais recentes revisados

- UI/configurações, run **36805504164**: análise concluída. Todos os cinco APKs
  têm métodos com erros JADX. SystemUX e SettingsPanelApp têm, cada um, um arquivo
  de origem acima do limite, omitido com caminho/tamanho/hash registrados.
- Clientes cloud, run **36805504240**: análise concluída. Store tem dois arquivos
  grandes omitidos; há erros JADX em Store, IdentityManagement, OCMS e SocialPlatform.
  DeviceAuthServer terminou sem erro de decompilação reportado, o que **não valida
  autenticação, execução ou acesso à nuvem**.
- Depth original, run **36805607831**: recursos extraídos/verificados, formato TH1
  ainda opaco. ARCore depth é outro backend, não execução desses modelos.
- Adaptadores Android, run **36805393417**: build/testes/lint passaram. Nenhum desses
  resultados comprova desempenho, inferência completa ou Horizon funcional no X6873.

Todos os estados públicos devem ser vinculados a testes reproduzíveis. Popularidade,
quantidade de Java reconstruído e workflow verde não são critérios de prontidão.
