# Identidade visual da demo

Nome solicitado: **MetaPort official demo by ahambolota**.

O PNG original foi importado da `main`, commit `6c2481a`, sem redesenhar ou alterar
o arquivo recebido. `branding.json` registra origem e hashes. A palavra “official”
foi mantida no nome solicitado pelo autor do projeto; não declara certificação da Meta.

`android-res/` contém ícones legacy de 48/72/96/144/192 px, ícone adaptativo com
margem adicional para máscaras do launcher e a string do nome. A arte não foi
recortada. Regeneração: Pillow 11.3.0 e `python3 -m tools.prepare_demo_branding`.

Estes recursos estão preparados, mas **ainda não estão aplicados ao APK original**.
Não alteramos silenciosamente os experimentos que verificam os recursos originais
byte a byte. Quando a etapa de empacotamento da beta permitir alterações explícitas
de identidade, ela deverá incorporar esses recursos e declarar as modificações.
Não criar uma Activity ou launcher substituto apenas para exibir o ícone.
