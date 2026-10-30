# Aray Zomboid Translator 0.4.0 — atualização majoritária

Ferramenta local para auditoria e complementação EN → PTBR dos arquivos de tradução do Project Zomboid B42. **Não altera a instalação do jogo**.

## Alterações em relação à 0.3.2

- Motor de trabalho separado (`arayzt/jobs.py`), com etapas de auditoria, tradução, validação e exportação.
- Botão de cancelamento cooperativo (encerra depois do lote atual) e exportação parcial validada.
- Retomada por checkpoint atômico associado a SHA256 do arquivo/chave/texto original.
- Limite de entradas por execução para fazer pilotos antes da tradução integral.
- Relatórios separados: `audit.json`, `summary.json`, `review.csv` (Excel), `accepted.json`, `checkpoint-v040.json`.
- KPIs filtrados, contador de traduções aceitas, fase atual, artefatos gerados e tabela por arquivo.
- Filtro exato de nomes: `UI,ContextMenu,Moodles` (nunca casa `SomeUI`).
- Exclusão de `SurvivorNames`, `Recorded_Media`, `RadioData` e entradas existentes na tradução automática.
- Ollama local com validação de placeholders; não envia dados para serviço remoto.
- `GET /api/health`, `GET /api/status`, `GET /api/preview`, `POST /api/cancel`.

## Windows

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m arayzt.cli dashboard
```

Painel: http://127.0.0.1:8767 — feche o painel anterior antes de iniciar.

### Atualizações do painel React

O React recebe snapshots de estado por SSE (`GET /api/events`), com reconexão
automática e consulta de `/api/status` como alternativa. KPIs, percentual, filas,
workers e decisões pertencem à mesma revisão do estado. O cabeçalho informa se a
conexão está em tempo real ou usando consultas periódicas. É preciso reiniciar o
backend depois de atualizar seu código; uma execução antiga não carrega rotas ou
campos novos automaticamente. Aguarde a conclusão ou cancele pelo painel antes
de reiniciar, preservando o checkpoint.

Os 1–4 workers configurados formam um pool compartilhado: Tradutor I faz novas
traduções, Tradutor II processa correções solicitadas pelo gerente. Qualquer worker
livre prioriza correções; o total de inferências simultâneas não ultrapassa o
limite escolhido. Sem correções, todos podem trabalhar como Tradutor I.

O orquestrador mostra entradas **pendentes**, incluindo as em execução. Os demais
cards mostram somente itens **na fila**, separados dos que estão em execução.
O log de decisões apresenta horário, agente, entrada, ciclo, resultado e motivo:
feito, aprovado, reprovado, análise automática, refazer ou cancelado. Entradas aprovadas
no checkpoint/glossário são identificadas como reutilizadas, sem inventar decisões
do gerente. Os últimos 120 eventos ficam no estado ao vivo; o histórico completo
das entradas é exportado ao final em `agent-history.json`.

No desenvolvimento, `VITE_BACKEND_URL` permite apontar o proxy do Vite para outra
instância local. O padrão continua sendo `http://127.0.0.1:8767`.

### Otimização de tradução

O painel permite lotes de 1, 2 ou 4 textos curtos. Textos longos e correções são
processados individualmente; cada saída do lote passa pela validação. Respostas
repetidas sem progresso seguem ao analista sem consumir uma terceira geração.
Pendências antigas de revisão são migradas ao analista, mesmo quando já houve
uma tentativa anterior. Não existe aprovação humana no fluxo. Falhas não
resolvidas ficam em `analysis-report.json`, com motivo, candidata e autoria.
Confira as medições históricas em [OPTIMIZATION_REPORT.md](OPTIMIZATION_REPORT.md).

### Analista local e auditoria completa

Falhas não resolvidas pelos tradutores seguem para o quinto worker, um analista
com presets e Argos Translate EN -> PT-BR offline. O gerente fornece diagnóstico
e contexto de correção ao Tradutor II; a saída do analista também é validada.
A entrega inclui `auditoria-traducao.csv` com antes/depois, autoria, tentativas,
motivos e confirmação de exportação. Consulte [ANALYST_WORKFLOW.md](ANALYST_WORKFLOW.md)
para instalar o modelo e entender a rastreabilidade e os casos não resolvidos.

Instalação real: `E:\Games\Project.Zomboid.v42.13.1\game\media\lua\shared\Translate`.

Primeiro execute **Somente auditar**; depois faça um piloto de **8 a 24 entradas** em `UI,ContextMenu,Moodles`, revise o `workspace/export`, e então expanda.

```powershell
.\.venv\Scripts\python.exe -m arayzt.cli audit --game "E:\Games\Project.Zomboid.v42.13.1\game\media\lua\shared\Translate" --work .\workspace --files UI,ContextMenu,Moodles
.\.venv\Scripts\python.exe -m arayzt.cli translate --game "E:\Games\Project.Zomboid.v42.13.1\game\media\lua\shared\Translate" --work .\workspace --files UI,ContextMenu,Moodles --limit 16 --batch 4
```

## Segurança e limitações

O parser Lua é conservador: preserva comentários e traduções existentes, mas não interpreta todas as expressões Lua ou textos livres. Duplicidades e linhas ambíguas ainda exigem revisão. Traduções idênticas podem ser legítimas. **A exportação é um diretório independente, não um mod automaticamente instalado**. Confira o resultado no jogo e mantenha um backup.
