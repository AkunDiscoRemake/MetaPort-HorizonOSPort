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

## Primeira recuperação verificada

Run **36805607831: sucesso na extração/inspeção**, não na execução de modelos.
Os dois `.ptl` começam com `54 48 31 00 00 00` (`TH1` seguido de zeros), não ZIP.
O parser os registrou como **UNKNOWN**: não há grafo/pesos decodificados nem
compatibilidade Torch/ExecuTorch demonstrada. Não carregar só por terem extensão
`.ptl`. Os hashes e tamanhos agora estão em `resource-policy.json`.

O tuning tem raízes `basic`, `convergence`, `factorization`, `metering`;
nomes de configuração não demonstram que o sensor correspondente existe no celular.
