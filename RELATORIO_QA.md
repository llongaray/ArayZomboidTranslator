# Aray Zomboid Translator — auditoria independente (30/10/2026)

## Resultado

- ZIP original recebido em 30/10/2026; correções de conteúdo aplicadas a um novo ZIP, sem modificar o original.
- Integridade estrutural declarada pelo Codex: 10.665 aprovadas e exportadas, 19 arquivos PTBR, 0 bloqueios.
- Este pacote aplica **65 correções adicionais revisadas** em 6 arquivos PTBR, e em suas respectivas representações de auditoria Lua.
- Nenhuma entrada adicionada ou excluída; todas as 10.665 aprovações e as 25.669 linhas de auditoria mantidas.
- Placeholders, marcadores estruturais e identificadores de chave preservados nas correções.
- Os 19 SHA-256 de arquivos nativos foram atualizados no manifesto.
- O checkpoint original do usuário **não foi modificado**. Se a aplicação reexportar do checkpoint, ela poderá restaurar traduções erradas. Importar `CORRECOES_QA.csv` no fluxo do projeto.

## Alterações por arquivo

- `Attributes_PTBR.txt`: 1
- `Entity_PTBR.txt`: 1
- `Farming_PTBR.txt`: 21
- `Fluids_PTBR.txt`: 29
- `IG_UI_PTBR.txt`: 7
- `MapLabel_PTBR.txt`: 6

## Casos críticos comprovados no pacote anterior

| Arquivo | EN | Antes | Depois |
|---|---|---|---|
| Farming | Tobacco | Bacon | Tabaco |
| Farming | May | Pode | Maio |
| Farming | Parsley | Pimenta sagu | Salsa |
| Farming | Hops | Saltos | Lúpulo |
| Fluids | Pan | Pão | Frigideira |
| Fluids | Mead | Mel | Hidromel |
| Fluids | Well | Bem | Poço |
| MapLabel | MULDRAUGH | MULDRAUGH GERENTE | MULDRAUGH |
| IG_UI | Attacker | Ataque | Atacante |

## Limitações e recomendações

1. **Não foi testado dentro do Project Zomboid**: não há execução do jogo nesta sessão. A semântica de 10.665 entradas não foi revisada uma a uma.
2. Há 9.651 registros aprovados com responsável original `unknown`; os que receberam QA passam a apresentar a revisão, mas a origem histórica das demais aprovações continua insuficiente.
3. O `export-diagnostics.json` original ainda registra avisos de sintaxe/duplicidade herdados dos arquivos preexistentes. Esses avisos devem ser tratados no carregador real, e não removidos às cegas.
4. O ZIP contém só 19 arquivos TXT regenerados, não todo o conjunto PTBR do jogo. **Não substitua a pasta de idioma inteira exclusivamente por este ZIP**. Faça backup e sobreponha somente os TXT presentes, preservando os demais arquivos e as traduções originais.
5. `auditoria-lua/` serve a validações, não deve ser copiada para o diretório do jogo.
6. A integração de alterações com checkpoint/gerente/supervisor deve manter histórico, diff e validação; não adotar uma simples substituição global em novas exportações.

## Anexos

- `CORRECOES_QA.csv`: diff de cada chave EN/PTBR, antes e depois.
- `qa-review.json`: registro estruturado das modificações.
- `auditoria-traducao.csv`: auditoria atualizada das correções.
- `delivery-manifest.json`: traduções corrigidas e hashes atualizados.
