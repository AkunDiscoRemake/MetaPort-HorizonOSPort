# Depth original Quest 3: separado do backend ARCore

Inventário do firmware 52168470052900520:

- system `/system/etc/mldepth/stereo_model.ptl` (5.502.172 bytes)
- system `/system/etc/mldepth/stereo_model_2.ptl` (7.669.175 bytes)
- odm `/etc/camera/depthaectuning.json` (56.657 bytes)

O workflow extrai esses recursos de partições verificadas e registra SHA-256,
metadados dos containers e strings de opcodes pickle, **sem carregar pickle ou
executar os modelos**. Isso não estabelece qual versão é ativa, se o modelo
consome as câmeras disponíveis no Infinix ou a ABI de entrada/saída. O nome
"stereo" é pista de investigação, não prova suficiente de contrato de entrada.

Para portar o depth original: recuperar o consumidor, calibração, formatos,
pré/pós-processamento e kernels, executar os pesos originais em backend compatível
e comparar com resultados de referência. Não duplicar uma imagem monocular e
chamar isso de estéreo. O VRBox não fornece sensores.

O backend opcional ARCore está em `port/android/DEPTH.md`: é uma adaptação Android
explicitamente diferente, não substituição oculta do algoritmo Meta.
