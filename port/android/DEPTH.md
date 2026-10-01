# Depth real no backend Android — não detector Quest portado

O VRBox é um suporte óptico: não acrescenta sensor ToF, câmeras estéreo ou sensores
Quest ao Infinix. `ArCoreTracking.supportsDepth` verifica o suporte da sessão no
aparelho. `configureDepth` opta explicitamente por AUTOMATIC ou RAW com a sessão
pausada. OFF permanece padrão para evitar custo desnecessário.

`withDepth` adquire as imagens reais da sessão ativa e empresta-as a um callback
síncrono. O fechamento é garantido mesmo em exceção; não há cópia de imagem para
Java, fila crescente ou segunda câmera. AUTOMATIC não recebe confiança fictícia;
RAW inclui confiança original 0..255 com checagem de tamanho/timestamp do par.
O timestamp de depth pode diferir do RGB; raw pode ser esparso/repetido.

`DepthPixels` lê milímetros unsigned little-endian respeitando position, limit,
rowStride e pixelStride. Zero significa ausência de medida, não superfície perto
da câmera. Coordenadas são da imagem depth, não da tela/olho. Uso:

```java
// Sessão criada, ainda pausada; CAMERA já consentida pelo usuário.
if (tracking.supportsDepth(ArCoreTracking.DepthMode.RAW)) {
    tracking.configureDepth(ArCoreTracking.DepthMode.RAW);
}
// Após resume(), textura/geometry configuradas e update():
tracking.withDepth((depth, confidence, colorTimestampNs, epoch) -> {
    // Usar getPlanes(), dimensões e depth.getTimestamp() aqui.
    // Não reter/fechar as imagens; não despachar trabalho assíncrono com elas.
});
```

Sem suporte ou sem imagem, não produzir valores substitutos. Isso NÃO implementa
o algoritmo Quest de depth, calibração, alinhamento à câmera RGB, reconstrução,
reprojeção por olho, oclusão das mãos ou compositor original. Não afirmar essas
funções a partir de build/testes. Precisa de validação física no X6873.
