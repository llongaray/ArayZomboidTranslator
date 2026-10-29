"""Dashboard local: jobs em threads com estado protegido."""
from flask import Flask, jsonify, render_template_string, request
from threading import Lock, Thread
from pathlib import Path
from .cli import execute
from .summary import summarize
import json

app = Flask(__name__)
_lock = Lock()
_state = {"status":"idle","progress":0,"total":0,"errors":0,"result":None,"message":"","summary":None}
HTML = '''<!doctype html><html lang="pt-br"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Aray Zomboid Translator</title><style>
:root{font-family:system-ui,Arial;background:#0b1322;color:#e7f0ff}body{margin:0 auto;max-width:1120px;padding:36px 20px}h1{margin:0}small,p{color:#a4b9d5}.panel{background:#142238;border:1px solid #2b4162;border-radius:16px;padding:22px;margin-top:22px}label{display:block;margin:12px 0 7px}input,select{width:100%;box-sizing:border-box;background:#0c172b;color:white;padding:12px;border:1px solid #426081;border-radius:9px}button{background:#ffc857;border:none;border-radius:9px;padding:13px 20px;font-weight:700;cursor:pointer;margin-top:20px}button:disabled{opacity:.5;cursor:wait}code{color:#f5d180}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#0b1322;padding:15px;border-radius:9px}progress{width:100%;height:20px} .note{border-left:3px solid #ffc857;padding:9px 14px;background:#24304a} .metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin:14px 0}.metric{background:#0b172a;border:1px solid #324763;border-radius:12px;padding:16px}.metric .num{font-weight:800;font-size:26px;overflow-wrap:anywhere}.metric .lab{font-size:12px;color:#a4b9d5}.panel-inner{margin-top:20px;border-top:1px solid #304360;padding-top:14px}.dist{display:flex;height:18px;border-radius:9px;overflow:hidden;background:#344055}.dist>span{min-width:0}.legend{display:flex;gap:15px;flex-wrap:wrap;margin-top:10px;font-size:12px}.legend span:before{content:' ';display:inline-block;width:10px;height:10px;margin-right:6px;background:var(--dot);border-radius:3px}table{width:100%;border-collapse:collapse;text-align:left;font-size:13px}td,th{padding:10px;border-bottom:1px solid #304360}td:not(:first-child),th:not(:first-child){text-align:right}.table-scroll{overflow-x:auto}details{margin-top:18px}summary{cursor:pointer;color:#f5d180}#activeFilters{font-size:12px} @media(max-width:600px){body{padding:18px 12px}.panel{padding:14px}} </style><h1>Aray Zomboid Translator</h1><p>Auditoria e tradução local para Project Zomboid B42 • Ollama</p>
<div class="panel"><form id="f"><label>Diretório de instalação do jogo (ou diretório Translate)</label><input name="game" placeholder="C:\\Games\\ProjectZomboid" required><label>Área de trabalho / saída</label><input name="work" value="./workspace" required><label>Modo</label><select name="mode"><option value="all">Auditoria completa</option><option value="review">Ausentes + idênticas ao inglês</option><option value="missing">Somente ausentes</option></select><label>Modelo Ollama</label><input name="model" value="gemma3:4b"><label>Filtrar arquivos (opcional: UI,ContextMenu,Moodles)</label><input name="files" value="UI,ContextMenu,Moodles" placeholder="UI,ContextMenu,Moodles"><label>Limite de entradas nesta execução (0 = todas)</label><input name="limit" type="number" min="0" value="0"><label>Itens por lote</label><input name="batch" type="number" min="1" max="64" value="8"><label>Endpoint local</label><input name="url" value="http://127.0.0.1:11434"><label>Operação</label><select name="operation"><option value="audit">Somente auditar (não chama IA)</option><option value="translate">Traduzir e exportar (chama Ollama)</option></select><button id="go">Executar</button> <button type="button" id="cancel" style="background:#e76f70">Cancelar tradução</button></form></div>
<div class="panel"><h2>Estado da execução</h2><p id="phase" aria-live="polite">Pronto</p><progress id="bar" value="0" max="100"></progress><p id="status">Aguardando operação</p><p id="batchStatus" aria-live="polite"></p><div id="kpiSection" hidden><div class="metrics" id="metrics"></div><div class="panel-inner"><h3>Cobertura da tradução <span id="coverage"></span></h3><div class="dist" id="distribution"></div><div class="legend" id="legend"></div></div><div class="panel-inner"><h3>Arquivos com mais pendências</h3><div class="table-scroll"><table><thead><tr><th>Arquivo</th><th>Ausentes</th><th>Traduzidas</th><th>Idênticas</th><th>Placeholders</th></tr></thead><tbody id="fileRows"></tbody></table></div></div><div class="panel-inner"><h3>Problemas do parser</h3><div class="metrics" id="problemMetrics"></div></div><p id="activeFilters"></p></div><div class="panel-inner"><h3>Controle de qualidade</h3><p>Traduções suspeitas ficam em <code>quality-review.json</code> e não são exportadas. Revisão humana necessária antes de instalar.</p><div class="metrics"><div class="metric"><div class="num" id="qaApproved">0</div><div class="lab">Aprovadas automaticamente</div></div><div class="metric"><div class="num" id="qaReview">0</div><div class="lab">Aguardando revisão</div></div><div class="metric"><div class="num" id="qaRejected">0</div><div class="lab">Rejeitadas</div></div></div></div><div class="panel-inner"><h3>Arquivos gerados</h3><p id="artifacts">Auditoria pendente.</p></div><details><summary>Mostrar detalhes técnicos / JSON</summary><pre id="result">Os arquivos do jogo não serão alterados.</pre></details><p class="note">Aviso: textos idênticos são candidatos, não necessariamente erros; faça revisão humana do pacote antes da instalação.</p></div>
<script>
const f=document.querySelector('#f'),go=document.querySelector('#go'),statusEl=document.querySelector('#status'),result=document.querySelector('#result'),bar=document.querySelector('#bar');
const $=id=>document.getElementById(id);const fmt=n=>Number(n||0).toLocaleString('pt-BR');
$('cancel').onclick=async()=>{const r=await fetch('/api/cancel',{method:'POST'});if(r.ok)$('phase').textContent='Cancelamento solicitado; finalizando o lote atual...';};
const colors={translated:'#32b88b',missing:'#e76f70',identical:'#e0ae52',placeholder_mismatch:'#a68af2'};
function metric(label,n){const el=document.createElement('div');el.className='metric';const value=document.createElement('div');value.className='num';value.textContent=fmt(n);const lab=document.createElement('div');lab.className='lab';lab.textContent=label;el.append(value,lab);return el;}
function renderSummary(s){if(!s){$('kpiSection').hidden=true;return;}$('kpiSection').hidden=false;const c=s.counts||{};const metrics=$('metrics');metrics.replaceChildren();[['Entradas analisadas',s.total],['Traduzidas',c.translated],['Ausentes',c.missing],['Idênticas',c.identical],['Placeholder divergente',c.placeholder_mismatch],['Selecionadas para IA',s.selected],['Problemas',s.problems],['Arquivos com entradas',s.files?.length]].forEach(([l,n])=>metrics.appendChild(metric(l,n)));
$('coverage').textContent=fmt(s.translated_pct)+'% traduzidas';const dist=$('distribution'),leg=$('legend');dist.replaceChildren();leg.replaceChildren();for(const [k,label] of [['translated','Traduzidas'],['missing','Ausentes'],['identical','Idênticas'],['placeholder_mismatch','Placeholders']]){const n=c[k]||0;if(!n)continue;const v=document.createElement('span');v.style.flex=String(n);v.style.background=colors[k];dist.appendChild(v);const l=document.createElement('span');l.style.setProperty('--dot',colors[k]);l.textContent=label+': '+fmt(n);leg.appendChild(l);}
const table=$('fileRows');table.replaceChildren();for(const row of (s.files||[]).slice(0,30)){const tr=document.createElement('tr');for(const k of ['file','missing','translated','identical','placeholder_mismatch']){const td=document.createElement('td');td.textContent=k==='file'?row[k]:fmt(row[k]);tr.appendChild(td);}table.appendChild(tr);}
const pm=$('problemMetrics');pm.replaceChildren();Object.entries(s.problem_counts||{}).sort((a,b)=>b[1]-a[1]).forEach(([k,n])=>pm.appendChild(metric(k,n)));
$('activeFilters').textContent='Filtro aplicado: '+(s.filters||'Nenhum (todos os arquivos)')+' • Arquivos fonte: '+fmt(s.source_files)+' • Analisados: '+fmt(s.parsed_files);
}
f.onsubmit=async e=>{e.preventDefault();const body=Object.fromEntries(new FormData(f));go.disabled=true;try{const r=await fetch('/api/start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const data=await r.json();if(!r.ok){result.textContent=JSON.stringify(data,null,2);go.disabled=false;}}catch(err){result.textContent=String(err);go.disabled=false;}};
setInterval(async()=>{try{const s=await(await fetch('/api/status')).json();bar.value=s.total?100*s.progress/s.total:(s.status==='done'?100:0);statusEl.textContent=s.status+' — '+fmt(s.progress)+'/'+fmt(s.total)+' — falhas: '+fmt(s.errors)+' — aprovadas: '+fmt(s.accepted)+' — revisão: '+fmt(s.needs_review);$('phase').textContent=s.phase||'idle';const elapsed=s.batch_started_at?Math.round(Date.now()/1000-s.batch_started_at):null;$('batchStatus').textContent=s.status==='running'&&s.phase==='translate'?(s.message||'Traduzindo')+(elapsed!==null?' • '+elapsed+'s no lote atual':'')+(s.batch_elapsed_seconds!=null&&!s.batch_started_at?' • último lote: '+s.batch_elapsed_seconds+'s':''):'';$('qaApproved').textContent=fmt(s.accepted);$('qaReview').textContent=fmt(s.needs_review);$('qaRejected').textContent=fmt(s.errors);$('artifacts').textContent=s.result?['audit','review_csv','accepted','quality_review','checkpoint','output'].filter(k=>s.result[k]).map(k=>k+': '+s.result[k]).join(' | '):'Aguardando arquivos';result.textContent=JSON.stringify(s.result??s.message,null,2);renderSummary(s.summary);go.disabled=s.status==='running'}catch{}},1000);
</script></html>'''

# Estado local; somente um trabalho simultâneo por processo.
from .jobs import Pipeline, Cancelled
from .summary import matches
from flask import send_file
from collections import Counter
import threading
_cancel = threading.Event()

@app.get('/api/preview')
def preview():
    with _lock:
        summary=_state.get('summary')
        result=_state.get('result')
    return jsonify(summary=summary,result=result)

@app.post('/api/cancel')
def cancel_job():
    with _lock:
        if _state['status'] != 'running':return jsonify(error='Nenhuma operação em andamento'),409
    _cancel.set()
    return jsonify(cancel_requested=True,message='Cancelamento solicitado; a requisição ativa tem limite de 35 segundos')

@app.get('/api/health')
def health():return jsonify(service='Aray Zomboid Translator',version='0.5.1',ok=True)

@app.get("/")
def index(): return render_template_string(HTML)

@app.get("/api/status")
def status():
    with _lock:return jsonify(dict(_state))

@app.post("/api/start")
def start():
    data = request.get_json(silent=True) or {}
    if not isinstance(data,dict): return jsonify(error="JSON inválido"),400
    with _lock:
        if _state["status"] == "running":return jsonify(error="Já existe uma execução ativa"),409
        _state.update(status="running",progress=0,total=0,errors=0,result=None,message="Inicializando",summary=None,phase="starting",accepted=0,needs_review=0,batch_started_at=None,batch_elapsed_seconds=None)
        _cancel.clear()
    try:
        game = str(data.get("game","")).strip()
        if not game: raise ValueError("Informe o diretório do jogo")
        batch = int(data.get("batch",8))
        if not 1 <= batch <= 64: raise ValueError("Lote inválido")
        mode = data.get("mode","all")
        if mode not in ("all","review","missing"):raise ValueError("Modo inválido")
        operation = data.get("operation","audit")
        if operation not in ("audit","translate"):raise ValueError("Operação inválida")
        args = (game,str(data.get("work","./workspace")),mode,str(data.get("model","gemma3:4b")),batch,str(data.get("url","http://127.0.0.1:11434")),operation=="translate")
    except (TypeError,ValueError) as exc:
        with _lock:_state["status"]="error"
        return jsonify(error=str(exc)),400
    def task():
        try:
            filters = str(data.get('files','')).strip()
            limit=int(data.get('limit',0) or 0)
            def event(**kw):
                with _lock:
                    for k,v in kw.items():
                        if k=='failed':_state['errors']=v
                        else:_state[k]=v
            result=Pipeline(event,_cancel).run(*args[:7],files=filters,limit=limit)
            report=json.loads(Path(result['audit']).read_text(encoding='utf-8'))
            summary=summarize(report,filters,result['selected'])
            with _lock:_state.update(status='cancelled' if result.get('cancelled') else 'done',result=result,summary=summary,message='Concluído')
        except Exception as exc:
            with _lock:_state.update(status='error',message=f'{type(exc).__name__}: {exc}')
    Thread(target=task,daemon=True).start()
    return jsonify(started=True),202
