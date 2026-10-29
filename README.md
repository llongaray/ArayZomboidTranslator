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

Instalação real: `E:\Games\Project.Zomboid.v42.13.1\game\media\lua\shared\Translate`.

Primeiro execute **Somente auditar**; depois faça um piloto de **8 a 24 entradas** em `UI,ContextMenu,Moodles`, revise o `workspace/export`, e então expanda.

```powershell
.\.venv\Scripts\python.exe -m arayzt.cli audit --game "E:\Games\Project.Zomboid.v42.13.1\game\media\lua\shared\Translate" --work .\workspace --files UI,ContextMenu,Moodles
.\.venv\Scripts\python.exe -m arayzt.cli translate --game "E:\Games\Project.Zomboid.v42.13.1\game\media\lua\shared\Translate" --work .\workspace --files UI,ContextMenu,Moodles --limit 16 --batch 4
```

## Segurança e limitações

O parser Lua é conservador: preserva comentários e traduções existentes, mas não interpreta todas as expressões Lua ou textos livres. Duplicidades e linhas ambíguas ainda exigem revisão. Traduções idênticas podem ser legítimas. **A exportação é um diretório independente, não um mod automaticamente instalado**. Confira o resultado no jogo e mantenha um backup.
