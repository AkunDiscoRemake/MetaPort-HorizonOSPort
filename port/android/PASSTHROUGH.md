# Passthrough físico: componente de saída, não UI substituta

`PassthroughRenderer` amostra a textura externa OES da **mesma sessão ARCore** de
`ArCoreTracking`. Não abre Camera2 concorrente e não faz conversão YUV→RGB na CPU,
`glReadPixels`, cópia de imagem para Java ou alocação de buffers por frame no código
próprio. O quadrilátero tem quatro vértices; somente 32 bytes de coordenadas UV são
atualizados no VBO. Rotação/crop são calculados por `Frame.transformCoordinates2d`,
não por rotação hardcoded ou espelhamento inventado.

## Contrato para o integrador original (não um aplicativo demo)

Na thread de renderização, com contexto GLES atual:

```java
PassthroughRenderer cameraBackground = new PassthroughRenderer();
ArCoreTracking tracking = new ArCoreTracking(context); // consentimento CAMERA prévio
tracking.setCameraTexture(cameraBackground.cameraTexture());
tracking.setDisplayGeometry(rotation, width, height);
tracking.resume();
// A cada frame: FBO alvo deve estar ligado; host limpa cor/profundidade.
ArCoreTracking.TrackingFrame observation = tracking.update();
boolean drawn = tracking.drawPassthrough(cameraBackground, 0, 0, width, height);
// Em false/falha, remover imagem antiga; não manter frame como câmera "ao vivo".
// Restaurar estado GL da UI e renderizar as camadas originais quando portadas.
```

O pass altera program, viewport, unidade de textura 0, atributos 0/1 (e VAO atual,
se houver), ARRAY_BUFFER, máscaras e blend/depth/cull/scissor. **O host deve
restabelecer seu estado GL**, inclusive depthMask, antes das camadas seguintes.
Não há consultas/restaurações de estado do driver por frame. Não altera FBO e não
limpa buffers automaticamente. Não chamar `update()` novamente entre obter a
observação e desenhar seu fundo. `pause()` e alterações de geometria/textura
invalidam o frame elegível; falha de update não preserva o frame anterior.

No onPause, parar o loop e pausar a sessão; fechar sessão e renderer na thread
proprietária, com o contexto original atual, antes de destruí-lo. Recriar renderer
e religar a textura após perda do contexto. ARCore continua responsável pela câmera.

## Limites que não devem ser ocultados

- É imagem **monocular** física; não é captura estéreo, depth, reprojeção por olho,
  oclusão das mãos ou passthrough equivalente ao Quest.
- Exige ARCore disponível, permissão e câmera utilizável. Compatibilidade real do
  Infinix X6873 ainda não foi validada; não há fallback Camera2 nesta etapa.
- Não requer pose TRACKING para mostrar um frame de câmera real; isso não autoriza
  sintetizar pose quando ARCore está PAUSED.
- Ainda não ligado ao compositor original, nem à inferência original de mãos.
  O módulo nativo `handtracking` permanece compartilhado pelo build MetaPort.
- Build/lint não validam shader no driver físico, timing, imagem ou consumo.
- Sem depth/calibração/projeção apropriada, não usar para navegação física segura.

Otimizações estruturais acima são implementadas; ganhos de FPS ou bateria **não
foram medidos**. O objetivo é baixo custo, não alegar "otimização máxima" sem perfil.
