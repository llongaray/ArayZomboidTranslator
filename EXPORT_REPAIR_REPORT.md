# Correção de exportação e auditoria — v0.10.2

## Resultado verificado

- 10.665 aprovações preservadas e efetivamente exportadas em 19 arquivos regenerados.
- 9.113 entradas antes bloqueadas verificadas individualmente no TXT e no CSV.
- Zero aprovações sem exportar; zero arquivos bloqueados; `delivery_status=success`.
- Os 14 arquivos anteriores continuam presentes; 5.763 chaves anteriores conferidas.
- 10.650 aprovações permaneceram idênticas. Quinze receberam correções contextuais
  documentadas, preservando o estado aprovado e a versão anterior no histórico/backup.
- Nenhuma inferência Ollama/Argos na operação de reexportação.

## Causas dos oito bloqueios

| Arquivo | Causa corrigida |
| --- | --- |
| EvolvedRecipeName | Chaves literais com pontos tratadas como identificadores Lua |
| IG_UI | Chaves com pontos e delimitadores legados, incluindo `;` |
| ItemName | Chaves com namespace e calibres numéricos, como `Base.223Box` |
| Moveables | Chaves iniciadas por números, espaços, apóstrofos e pontuação |
| RecipeGroups | Cabeçalho legado `RecipeGroupsEN {` sem `=` |
| Recipes | Chaves com pontos/calibres e pontuação |
| Stash | Comentários de bloco `/* ... */` indevidamente enviados ao parser Lua |
| SurvivalGuide | Aspas internas, concatenações, `..,` e fechamentos anexados às entradas |

## Formato do jogo e Lua

O carregador desta instalação (`zombie.core.Translator.parseFile`, inspecionado
com `javap` no JAR local) obtém a chave do lado esquerdo do `=` e o valor entre a
primeira e a última aspa. Não avalia os TXT como tabelas Lua. Converter uma chave
literal para `["..."]` altera a chave lida pelo jogo; adicionar escapes Lua ao
valor também altera o texto lido. Referência da classe oficial:
https://projectzomboid.com/modding/zombie/core/Translator.html

Os TXT gerados preservam chaves e valores literais no formato nativo. Cada arquivo
possui uma representação Lua estrita em `workspace/lua-certified/PTBR`, com chaves
especiais entre colchetes e strings escapadas. As 19 representações passam pelo
`luaparser`, sem executar Lua; não substituem os TXT instaláveis. Comentários são
arquivados com delimitadores seguros; dados dentro de comentários não viram novas
traduções ativas. Expressões não suportadas bloqueiam o arquivo.

## Segurança da exportação

A candidata é construída em arquivo temporário. Somente após verificar estrutura,
valores, preservação das entradas existentes e representação Lua, ela substitui o
destino. Uma candidata inválida vai à quarentena sem apagar uma entrega anterior.
O manifesto contém cada entrada exportada e o SHA-256 de cada arquivo. A auditoria
CSV confere manifesto e valor realmente relido; a existência de um TXT antigo não
é suficiente para classificá-lo como entregue.

## Retomada e KPIs

No React, selecione **Exportar checkpoint aprovado**, ou execute:

```powershell
.\.analyst-venv\Scripts\python.exe -m arayzt.cli export --work ./workspace
```

A operação verifica fonte EN e checkpoint antes de exportar. Não cria workers de
tradução. Os KPIs separam aprovadas, exportadas, aprovadas sem exportar e arquivos
bloqueados. `delivery_status=partial` impede conclusão, inclusive com lista de
bloqueios vazia. A porcentagem continua representando entradas processadas.

## Auditoria linguística

Houve triagem automática das 10.665 aprovações e revisão contextual das 11 entradas
de BodyParts e de seis casos adicionais. Foram corrigidas nove entradas de
BodyParts: coluna vertebral, coxas, pernas, braços e antebraços com lateralidade.
Os seis casos adicionais incluem quatro omissões de lateralidade em armaduras,
"Magazine" confundido com arma e "chiqueiro" usado no contexto das galinhas.
A triagem não constitui certificação semântica integral das outras traduções.

| Chave BodyParts | Anterior | Revisada |
| --- | --- | --- |
| BODYPART_PELVIS | Pelve | Pelve |
| BODYPART_SPINE | Espinha | Coluna vertebral |
| BODYPART_HEAD | Cabeça | Cabeça |
| BODYPART_LEFT_UPPER_LEG | Meia perna superior esquerda | Coxa esquerda |
| BODYPART_LEFT_LOWER_LEG | Meia inferior esquerda | Perna esquerda |
| BODYPART_RIGHT_UPPER_LEG | Membrana Superior da Coxa | Coxa direita |
| BODYPART_RIGHT_LOWER_LEG | Meia perna inferior | Perna direita |
| BODYPART_LEFT_UPPER_ARM | Braço Superior Esquerdo | Braço esquerdo |
| BODYPART_LEFT_LOWER_ARM | Braço Inferior Esquerdo | Antebraço esquerdo |
| BODYPART_RIGHT_UPPER_ARM | Braço Superior Direito | Braço direito |
| BODYPART_RIGHT_LOWER_ARM | Braço Inferior Direito | Antebraço direito |

As decisões estão vinculadas ao arquivo, chave e EN exatos. Alterações da fonte
invalidam a aplicação da regra. O checkpoint original e a entrega anterior estão
em `workspace/export-repair-backup/20261030-014708`, com manifesto SHA-256. Correções
linguísticas também criam snapshots próprios antes de persistir.

## Verificação

- 136 testes passaram: chaves com pontos e caracteres especiais, palavras reservadas,
  comentários, aspas, delimitadores, concatenação, fontes inválidas, placeholders,
  preservação de entregas anteriores e retomada sem modelos.
- Build TypeScript/Vite passou.
- API via proxy React, SSE e download do CSV conferidos.
- ZIP reaberto e todos os CRCs conferidos.
- `workspace/export-verification.json` registra a comparação com o backup inicial.

Artefatos: `export-diagnostics.json`, `delivery-manifest.json`,
`auditoria-traducao.csv`, `linguistic-audit.json`, `export-verification.json` e
`entrega-traducao.zip`, todos no workspace.
