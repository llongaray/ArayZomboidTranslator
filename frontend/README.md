# Dashboard React v0.9.2

React + TypeScript + Motion, com visualização do fluxo multiagente. A interface usa os endpoints existentes do Flask, sem tocar nos arquivos de tradução do jogo.

## Inicialização

Em um terminal na raiz do repositório:

```powershell
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m arayzt.cli dashboard
```

Em outro terminal:

```powershell
cd frontend
npm install
npm run dev
```

Abra **http://127.0.0.1:5173**. O Vite encaminha `/api` para `http://127.0.0.1:8767`.

Para compilar para distribuição: `npm run build`.

O estado visual usa a última etapa reportada em `/api/status`. Ainda não há WebSocket por estágio nem cronômetro por token. A interface Flask anterior permanece disponível na porta 8767.
