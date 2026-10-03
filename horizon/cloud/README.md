# Clientes Meta online — análise original, backend não portado

Escopo inicial verificável no firmware 52168470052900520/system_ext:
Store, IdentityManagement, DeviceAuthServer, OCMS e SocialPlatform. O workflow
`cloud-client-analysis.yml` extrai da partição verificada e decompila os clientes
originais, incluindo manifestos, dependências ELF e candidatos de chamadas de
identidade, compras/entitlements, instalação e serviços privilegiados.

**Não executa APKs, não faz login, não contata APIs Meta, não captura credenciais e
não simula contas, compras ou direitos de uso.** Nomes de classes/strings não provam
que a Store pode funcionar no Android alvo. Tokens citados em código não são
credenciais de usuário e não são usados para autenticação.

## Fronteira de portabilidade

- Cliente: DEX, JNI, recursos, Binder e requisitos de permissões precisam ser
  recuperados e ligados ao runtime. Não é suficiente abrir um WebView da Store.
- Servidor: catálogo, conta, compras, entitlement, serviços sociais e políticas
  de dispositivo são controlados pela Meta; não estão dentro da OTA.
- Credenciais de assinatura/atestação do Quest não são fabricadas ou extraídas
  de outro aparelho. Dependência de API privada/privilegiada é bloqueio explícito.
- O APK comum não herda permissões signature/privileged nem pode atuar como
  instalador/serviço de sistema sem suporte permitido pelo Android.
- Integração online exige fluxo autorizado, configuração de app/dispositivo e
  condições de serviço válidas. Esta análise não demonstra que isso foi obtido.

Resultado: `analysis/builds/52168470052900520/ui-cloud-decompilation.json`.
Relatório de candidatos não é um port dos serviços cloud e nunca habilita um
indicador de "Store funcional" sozinho. Fontes reconstruídas podem ter erros.

## Autorização declarada e integração técnica

O responsável pelo projeto declarou autorização para usar os servidores Meta.
Essa declaração não foi verificada independentemente e não é tratada como uma
negativa de autorização. Também não comprova, por si só, que o cliente Android
já esteja registrado, autenticado ou aceito pelos serviços.

Para implementar a integração autorizada, ainda faltam contratos técnicos:
SDK/documentação de endpoints e versões, métodos de autenticação e escopos,
registro de aplicativo/dispositivo, requisitos de assinatura/atestação e ambiente
de testes aprovado. Esses itens devem vir da documentação/acesso fornecido pela
Meta, não ser inventados a partir de nomes encontrados no binário. Documentação
pública ou arquivos sanitizados podem orientar o port; credenciais não devem ser
colocadas no chat, no repositório, no APK ou nos relatórios. A extração atual
continua offline e não usa tokens encontrados nos clientes originais.
