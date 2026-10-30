# Analista local e auditoria da entrega

## Fluxo

1. Tradutor I produz uma candidata; supervisor valida estrutura, marcadores e regras.
2. Gerente descreve o defeito e prepara contexto para o Tradutor II: arquivo,
   chave, EN, falhas, marcadores esperados, ausentes e extras, e instruções de reparo.
3. Repetição sem progresso, limite de tentativas ou candidata estruturalmente
   rejeitada segue para a fila do analista. Fonte inválida e falha de infraestrutura
   não são confundidas com um problema linguístico recuperável. Se o Ollama ficar
   indisponível, as filas restantes seguem diretamente ao analista offline; se
   ele também falhar, o motivo de infraestrutura é preservado no resultado.
4. O analista tenta presets seguros (glossário revisado e reparo de prefixo interno
   quando a candidata corrigida passa na validação). Depois usa Argos EN -> PT-BR.
5. O gerente aprova a saída validada ou registra uma falha com motivo, sem encaminhamento humano.
   Não há ciclo infinito entre analista e Tradutor II. Cada entrada visita o
   analista no máximo uma vez por processamento.

Os quatro workers Ollama continuam compartilhados pelos tradutores I e II.
O analista tem uma fila independente e um quinto worker; usa CPU, int8 e duas
threads internas de inferência, sem carregar outro modelo na GPU do Ollama.

## Biblioteca e instalação

Argos Translate é a biblioteca offline; o pacote oficial `en_pb` é específico
para português brasileiro. Tokenizador e CTranslate2 são executados diretamente
sobre os fragmentos já delimitados, evitando downloads de segmentadores durante
a tradução. Modelos e cache ficam em `workspace/analyst-models` e
`workspace/analyst-runtime`. Não são enviados textos a serviços de tradução.

Em um ambiente Python funcional, instale com:

```powershell
python -m pip install -e ".[analyst]"
python -m arayzt.analyst_setup
python -m arayzt.cli dashboard
```

Nesta máquina foi criado `.analyst-venv`, porque a `.venv` anterior aponta para
um Python que não está mais disponível. `run-dashboard.bat` prefere o ambiente
do analista quando ele existe. O ambiente e os modelos não são versionados.

`GET /api/analyst/status` informa instalação do modelo e disponibilidade da
biblioteca. Se houver falha de biblioteca/modelo, ela será registrada; a execução
não inventa uma tradução nem muda automaticamente para um serviço online.

## Presets e limites

- Exceções revisadas precisam coincidir com chave e fonte original.
- Remover `K1 -` de uma candidata só é um reparo aprovado se o texto restante
  passar na validação; remover o prefixo de inglês não o transforma em PT-BR.
- Marcadores, tags e quebras de linha não são enviados ao tradutor offline.
- Pontos finais acrescentados pelo motor a fragmentos curtos de UI são removidos
  quando a fonte não os contém, sem remover a pontuação original.
- Uma saída vazia, truncada, com marcadores alterados ou sem tradução permanece
  com motivo. Aprovação heurística não é uma certificação de equivalência semântica.

Pendências antigas são migradas diretamente ao analista, inclusive quando já
passaram pelo motor anterior. O hash de arquivo/chave/EN invalida candidatas
quando a fonte muda. Falhas persistem em `analysis-report.json` e, na retomada,
voltam ao analista sem repetir chamadas ao Ollama.

A política v2 em `arayzt/data/analyst_cases_ptbr.json` contém decisões vinculadas
à chave e ao EN exato: nomes próprios preservados, palavras válidas em PT-BR e
traduções por contexto (por exemplo, Bill → Fatura no correio e Buck → Cervo macho
no tipo de animal). Não há permissão genérica para aprovar texto igual ao inglês.
A mesma palavra em outra chave continua sujeita à validação comum.

O painel substitui a aba de aprovação manual pelo acompanhamento do analista.
`GET /api/analyst/report` lista falhas com motivo. Rotas antigas `/api/review/*`
respondem HTTP 410 e decisões manuais históricas não alteram a entrega.

## Entrega

Além dos arquivos exportados, cada execução gera `auditoria-traducao.csv` (UTF-8
com BOM, separador `;`). O botão de download fica na aba Entrega; rota:
`GET /api/delivery/audit.csv?work=...`.

O CSV inclui todas as entradas da auditoria, não somente pendências: arquivo,
chave, EN, PT-BR anterior, PT-BR depois, candidata, responsável, provedor,
status, confirmação de exportação, motivo, tentativas dos dois motores,
diagnóstico/plano do gerente e histórico completo.

`ptbr_depois` representa o resultado efetivamente exportado. Uma candidata
aprovada em arquivo bloqueado aparece em `candidata`, com exportação `nao` e
motivo; não é apresentada como entregue. Valores que parecem fórmulas recebem
um apóstrofo de proteção para abertura em planilhas.

Responsáveis: `translator` (I), `translator_ii` (II), `analyst`, `preset`,
`original_ptbr`, `none` ou `unknown`. O provedor identifica o modelo Ollama ou a
versão do Argos. Checkpoints antigos sem autoria ficam como `unknown`, sem atribuir
retroativamente sua tradução a um agente. Autoria nova é preservada nas retomadas.

## Verificação

- 116 testes: proteção de marcadores, isolamento de falhas, quinta execução
  simultânea, ausência de loop, diagnóstico do gerente, origem e exportação real.
- Integração com Argos real: Babá, Açougueiro, marcadores preservados, atribuição
  aos tradutores I/II e analista, falha justificada e retomada sem regeneração.
- CSV e arquivos de teste em `workspace/analyst-system-test-v2/output/`.

## Resultado da execução real

Rodada concluída: 10.064 candidatas aprovadas, 594 pendências após análise e
7 falhas. O analista tem autoria registrada em 332 aprovações adicionais.
A entrega final é parcial: 10 arquivos validados, contendo 1.464 traduções novas;
8 arquivos foram bloqueados pelo exportador/validador Lua. Outras 8.600 candidatas
aprovadas não são apresentadas como entregues no CSV.

A auditoria gerada tem 25.669 linhas. Os 9.673 registros sem autoria histórica
suficiente aparecem como `unknown`; isso não foi atribuído retroativamente ao
analista. Pacote válido em `workspace/entrega-traducao.zip`, sem arquivos de
quarentena nem artefatos remanescentes de execuções anteriores. O próximo trabalho
recomendado é adequar a exportação/validação aos formatos reais de tradução do jogo,
incluindo chaves com pontos e arquivos de formato especial; não remover a validação
para contornar os bloqueios. Também vale isolar a pasta de saída por execução.
