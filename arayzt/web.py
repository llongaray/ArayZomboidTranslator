"""Dashboard local: jobs em threads com estado protegido."""
from flask import Flask, jsonify, render_template_string, request, Response
from threading import Lock, RLock, Condition, Thread
from pathlib import Path
from .cli import execute
from .summary import summarize
from .manual_review import pending_review, record_decision
import json
import time
import uuid

app = Flask(__name__)
_lock = RLock()
_changed = Condition(_lock)
_revision = 0
_state = {"status":"idle","progress":0,"total":0,"errors":0,"result":None,"message":"","summary":None}
def _publish(**values):
    """Publish one atomic status revision to polling and SSE subscribers."""
    global _revision
    with _changed:
        for key,value in values.items():
            _state['errors' if key=='failed' else key]=value
        _revision+=1
        _state['revision']=_revision
        _state['updated_at']=time.time()
        _changed.notify_all()

HTML = '''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Aray Zomboid Translator</title>
<style>
:root{color-scheme:dark;font-family:Inter,Segoe UI,Arial,sans-serif;background:#091524;color:#eaf3ff}*{box-sizing:border-box}body{margin:0;min-width:320px}main{max-width:1600px;margin:auto;padding:18px 24px}.top{display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap;padding:14px 25px;border-bottom:1px solid #1e3856;background:#0c1b2e}.brand{display:flex;align-items:center;gap:14px}.brand-icon{color:#ffcb4a;border:1px solid #dba72d;border-radius:10px;padding:9px;font-size:25px}.brand h1{font-size:23px;margin:0}.brand strong{color:#ffcc50}.top small{color:#91a6c1}.pill{background:#12273d;border:1px solid #294663;padding:9px 13px;border-radius:9px}.online{color:#30d3a0}.panel{background:#102035;border:1px solid #29445e;border-radius:13px;padding:18px;margin-bottom:15px}h2{font-size:18px;margin:0 0 8px}h3{font-size:15px;margin:0 0 10px}p,.muted{color:#a6b9ce;font-size:13px}.layout{display:grid;gap:14px}.overview{display:grid;grid-template-columns:minmax(230px,1fr) minmax(240px,1.1fr) minmax(160px,.7fr);align-items:center;gap:20px}.big{font-size:34px;font-weight:800}.percent{color:#ffcc50}.track{height:11px;background:#314155;border-radius:20px;overflow:hidden}.fill{height:100%;width:0;background:#ffcb4a;transition:width .5s}.count{color:#abbfd5;font-size:13px}.flow{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:15px;margin-top:18px}.node{border:1px solid var(--clr);border-radius:13px;padding:18px 12px;background:#10253a;position:relative;min-height:132px;transition:transform .2s,box-shadow .2s}.node:hover{transform:translateY(-2px);box-shadow:0 5px 22px #0004}.node:not(:last-child):after{content:'→';position:absolute;right:-19px;top:42%;color:#36a7ff;font-size:22px;z-index:1}.node .glyph{font-size:24px;color:var(--clr)}.node h3{margin:8px 0}.node p{margin:4px 0}.feedback{border:1px dashed #b34b66;color:#ff8198;border-radius:9px;padding:10px;text-align:center;margin:14px auto 0;max-width:560px;font-size:12px}.metrics{display:grid;grid-template-columns:repeat(8,minmax(0,1fr));gap:10px}.metric{background:#11243a;border:1px solid #28425f;border-radius:11px;padding:13px;min-width:0}.metric .num{font-size:24px;font-weight:800}.metric .lab{color:#aabdd2;font-size:12px}.bottom{display:grid;grid-template-columns:1.05fr 1.1fr;gap:15px}.subgrid{display:grid;grid-template-columns:1.5fr 1fr;gap:15px}table{width:100%;border-collapse:collapse;font-size:12px}td,th{text-align:left;padding:10px 7px;border-bottom:1px solid #294158;overflow-wrap:anywhere}th{color:#a2b5cd}.scroll{max-height:280px;overflow:auto}.controls{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}label{font-size:12px;color:#b6c8dc;display:block}input,select,textarea{display:block;width:100%;margin-top:5px;background:#0b1829;border:1px solid #35526f;border-radius:7px;color:white;padding:10px;font:inherit}button{border:1px solid #3f6282;border-radius:8px;background:#166bdb;color:white;padding:10px 15px;cursor:pointer}button:hover{filter:brightness(1.15)}button:disabled{opacity:.5;cursor:not-allowed}.buttons{display:flex;gap:10px;margin-top:13px}.danger{background:#9b3a52}.small{font-size:12px}.status{color:#ffcb4a}.segment{display:flex;height:12px;border-radius:7px;overflow:hidden;background:#293b50}.segment span{height:100%}details summary{cursor:pointer;color:#ffcb4a}pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:240px;overflow:auto}.logs{max-height:230px;overflow:auto;font-size:12px;color:#b5c8d9}.log{border-bottom:1px solid #253d58;padding:6px}.review{border:1px solid #28445f;border-radius:9px;padding:10px;margin:9px 0}textarea{min-height:65px}.dot{display:inline-block;width:9px;height:9px;border-radius:100%;background:#25d7a1;margin-right:7px}#exportWarning{color:#ffce77} @media(max-width:1000px){.metrics{grid-template-columns:repeat(4,1fr)}.overview,.bottom,.subgrid{grid-template-columns:1fr}.flow{grid-template-columns:repeat(3,minmax(0,1fr))}.node:after{display:none}}@media(max-width:620px){main{padding:10px}.metrics,.controls,.flow{grid-template-columns:repeat(2,minmax(0,1fr))}.top{padding:12px}.big{font-size:27px}}@media(prefers-reduced-motion:reduce){*{transition:none!important}}
</style></head><body>
<header class="top"><div class="brand"><div class="brand-icon">▣</div><div><h1>Aray <strong>Zomboid</strong> Translator <small>v0.9.1</small></h1><small>Tradução local com orquestração de agentes</small></div></div><div class="pill"><span id="ollamaDot" class="dot" style="background:#ffcb4a"></span><span id="ollamaState" role="status">Verificando Ollama…</span></div></header>
<main><section class="panel"><form id="f"><div class="controls"><label>Diretório do jogo<input name="game" required placeholder="E:\Games\Project.Zomboid...\Translate"></label><label>Workspace<input name="work" required value="./workspace"></label><label>Modelo<input name="model" value="gemma3:4b"></label><label>Endpoint Ollama<input name="url" value="http://127.0.0.1:11434"></label><label>Workers (1–4)<input name="workers" type="number" value="1" min="1" max="4"></label><label>Itens por lote<input name="batch" type="number" value="4" min="1" max="32"></label><label>Limite (0 = todos)<input name="limit" type="number" value="0" min="0"></label><label>Filtro<input name="files" value="UI,ContextMenu,Moodles"></label><label>Auditoria<select name="mode"><option value="all">Completa</option><option value="missing">Somente ausentes</option><option value="review">Revisão</option></select></label><label>Operação<select name="operation"><option value="audit">Somente auditar</option><option value="translate">Traduzir e exportar</option></select></label></div><div class="buttons"><button id="go">Executar</button><button id="cancel" type="button" class="danger">Cancelar</button></div></form></section>
<section class="panel overview"><div><h2 id="headline">Pronto para executar</h2><p id="message">Aguardando início da auditoria.</p></div><div><div class="big percent" id="percent">0,0%</div><div class="track"><div id="progressFill" class="fill"></div></div><p id="processed">0 / 0 entradas processadas</p></div><div><p id="totals">Aprovadas: 0 | Revisão: 0 | Falhas: 0</p><p id="phase">idle</p><p id="workersActive">1 instância</p></div></section>
<section class="panel"><h2>Pipeline de agentes</h2><p>O orquestrador distribui entradas; o supervisor valida; o gerente solicita correção ou libera a entrega.</p><div class="flow"><div class="node" style="--clr:#a477fa"><span class="glyph">♛</span><h3>Orquestrador</h3><p id="nodeOrchestrator">Aguardando</p><p>Distribuição dos workers</p></div><div class="node" style="--clr:#318fff"><span class="glyph">▤</span><h3>Tradutor</h3><p id="nodeTranslator">Ollama local</p><p>Tradução atômica</p></div><div class="node" style="--clr:#2fd6a4"><span class="glyph">⬡</span><h3>Supervisor</h3><p id="nodeSupervisor">Aguardando</p><p>Qualidade e placeholders</p></div><div class="node" style="--clr:#ffca4a"><span class="glyph">✓</span><h3>Gerente</h3><p id="nodeManager">Aguardando</p><p>Decisão e feedback</p></div><div class="node" style="--clr:#29d6ac"><span class="glyph">⚑</span><h3>Entrega</h3><p id="nodeDelivery">Não iniciada</p><p>Validação dos arquivos Lua</p></div></div><div class="feedback">↺ Reprovação → contexto do gerente → retradução → nova supervisão (até 3 ciclos) → revisão humana, se necessário</div></section>
<section class="metrics" id="metrics"></section>
<div class="bottom" style="margin-top:15px"><section class="panel"><h2>Fila e histórico dos agentes</h2><p id="agentCount">Dados de execução</p><div class="scroll"><table><thead><tr><th>Arquivo / chave</th><th>Estágio</th><th>Ciclos</th><th>Resultado</th></tr></thead><tbody id="queueRows"></tbody></table></div></section><section class="panel"><h2>Cobertura da tradução original</h2><div class="segment" id="coverageBar"></div><p id="coverageLabel">Aguardando auditoria</p><details><summary>Arquivos com pendências</summary><div class="scroll"><table><thead><tr><th>Arquivo</th><th>Ausentes</th><th>Traduzidas</th></tr></thead><tbody id="fileRows"></tbody></table></div></details><h3 style="margin-top:20px">Atividade em tempo real</h3><div id="logs" class="logs"></div></section></div>
<div class="bottom"><section class="panel"><h2>Entrega e arquivos</h2><p id="exportWarning"></p><p id="artifacts">Nenhum arquivo gerado nesta sessão.</p><div id="blocked"></div><details><summary>Detalhes técnicos</summary><pre id="technical"></pre></details></section><section class="panel"><h2>Revisão humana</h2><p>Itens que esgotaram as tentativas automáticas; aprovações exigem intervenção explícita.</p><button id="reviewLoad" type="button">Carregar pendências</button><div id="reviewRows" class="scroll"></div></section></div></main>
<script>
const $=id=>document.getElementById(id),f=$('f'),fmt=n=>Number(n||0).toLocaleString('pt-BR');let previousKey='';
function kpi(label,val,color){const d=document.createElement('div');d.className='metric';if(color)d.style.borderColor=color;const a=document.createElement('div');a.className='num';a.textContent=fmt(val);const b=document.createElement('div');b.className='lab';b.textContent=label;d.append(a,b);return d}
function render(s){const sum=s.summary||{},c=sum.counts||{},t=Number(s.total||0),p=Number(s.progress||0),pct=t?100*p/t:(s.status==='done'?100:0);$('percent').textContent=pct.toFixed(1).replace('.',',')+'%';$('progressFill').style.width=Math.max(0,Math.min(100,pct))+'%';$('processed').textContent=fmt(p)+' / '+fmt(t)+' entradas processadas';$('totals').textContent='Aprovadas: '+fmt(s.accepted)+' | Revisão: '+fmt(s.needs_review)+' | Falhas: '+fmt(s.errors);$('headline').textContent=({running:'Execução em andamento',done:'Processamento concluído',partial:'Entrega parcial',error:'Falha na execução',cancelled:'Execução cancelada',idle:'Pronto para executar'})[s.status]||'Preparando';$('message').textContent=s.message||'Aguardando';$('phase').textContent=s.phase||'idle';$('workersActive').textContent=fmt(s.workers||1)+' instância(s)';$('nodeOrchestrator').textContent=fmt(p)+' / '+fmt(t);$('nodeTranslator').textContent=s.status==='running'?'Traduzindo':'gemma3:4b';$('nodeSupervisor').textContent=s.status==='running'?'Validando entradas':'Aguardando';$('nodeManager').textContent=fmt(s.needs_review)+' para revisão humana';$('nodeDelivery').textContent=s.phase==='export'?'Validando exportação':(s.result?.files!=null?fmt(s.result.files)+' arquivo(s)':'Aguardando');$('exportWarning').textContent=s.result?.blocked_files?.length?'Arquivos bloqueados pela validação: '+s.result.blocked_files.length:(s.result?.export_error||'');$('blocked').textContent=(s.result?.blocked_files||[]).map(x=>x.file+': '+(x.issue_count||0)+' problema(s)').join(' | ');$('artifacts').textContent=s.result?['audit','accepted','quality_review','agent_history','quality_invalidation','output'].filter(k=>s.result[k]).map(k=>k+': '+s.result[k]).join(' | '):'Aguardando arquivos';$('technical').textContent=JSON.stringify(s.result||s.message,null,2);
const m=$('metrics');m.replaceChildren();[['Aprovadas',s.accepted,'#219b78'],['Revisão humana',s.needs_review,'#b38b31'],['Falhas',s.errors,'#ad4561'],['Selecionadas',sum.selected,''],['Traduzidas na origem',c.translated,''],['Ausentes na origem',c.missing,''],['Idênticas',c.identical,''],['Placeholders',c.placeholder_mismatch,'']].forEach(x=>m.append(kpi(...x)));
const bar=$('coverageBar');bar.replaceChildren();const total=Number(sum.total||0);[['translated','#26cc99'],['missing','#b6c9e4'],['identical','#a77bfa'],['placeholder_mismatch','#ffbf49']].forEach(([k,color])=>{const e=document.createElement('span');e.style.width=(total?100*(c[k]||0)/total:0)+'%';e.style.background=color;bar.appendChild(e)});$('coverageLabel').textContent=total?'Origem: '+fmt(c.translated)+' traduzidas de '+fmt(total)+' ('+(100*(c.translated||0)/total).toFixed(1)+'%)':'Aguardando auditoria';f.querySelector('#go').disabled=s.status==='running';
const fileRows=$('fileRows');fileRows.replaceChildren();for(const entry of (sum.files||[])){const tr=document.createElement('tr');for(const v of [entry.file,fmt(entry.missing),fmt(entry.translated)]){const td=document.createElement('td');td.textContent=String(v);tr.appendChild(td)}fileRows.appendChild(tr)}
const rows=$('queueRows');rows.replaceChildren();for(const item of (s.agent_recent||[]).slice().reverse()){const tr=document.createElement('tr');const history=item.history||[];const last=history[history.length-1]||{};for(const value of [item.file+' / '+item.key,last.agent||'orquestrador',history.filter(h=>h.agent==='translator').length,item.status]){const td=document.createElement('td');td.textContent=String(value||'');tr.appendChild(td)}rows.appendChild(tr)}
const key=[s.status,p,s.phase,s.message,s.accepted,s.needs_review,s.errors].join('|');if(key!==previousKey){previousKey=key;const line=document.createElement('div');line.className='log';line.textContent=new Date().toLocaleTimeString('pt-BR')+' • '+(s.message||s.phase||s.status);$('logs').prepend(line);while($('logs').children.length>60)$('logs').lastChild.remove()}}
async function refresh(){try{const r=await fetch('/api/status');if(r.ok)render(await r.json())}catch{}}
f.onsubmit=async e=>{e.preventDefault();const body=Object.fromEntries(new FormData(f));$('go').disabled=true;try{const r=await fetch('/api/start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const data=await r.json();if(!r.ok){alert(data.error||'Erro');$('go').disabled=false}}catch(e){alert(String(e));$('go').disabled=false}};
$('cancel').onclick=async()=>{const r=await fetch('/api/cancel',{method:'POST'});if(!r.ok){const x=await r.json();alert(x.error||'Erro')}};
$('reviewLoad').onclick=async()=>{const work=f.elements.work.value,r=await fetch('/api/review?work='+encodeURIComponent(work)),data=await r.json(),root=$('reviewRows');root.replaceChildren();if(!r.ok){root.textContent=data.error||'Erro';return}for(const item of data.items){const box=document.createElement('div');box.className='review';const title=document.createElement('h3');title.textContent=item.file+' / '+item.key;const en=document.createElement('p');en.textContent='EN: '+(item.english||'');const textarea=document.createElement('textarea');textarea.value=item.translation||'';const feedback=document.createElement('p');box.append(title,en,textarea);for(const action of ['approve','reject']){const b=document.createElement('button');b.type='button';b.textContent=action==='approve'?'Aprovar':'Rejeitar';if(action==='reject')b.className='danger';b.onclick=async()=>{const resp=await fetch('/api/review/decision',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({work,file:item.file,key:item.key,translation:textarea.value,action})});const x=await resp.json();feedback.textContent=resp.ok?'Decisão salva':x.error||'Erro'};box.append(b)}box.append(feedback);root.append(box)}};
async function checkOllama(){try{const query=new URLSearchParams({model:f.elements.model.value,url:f.elements.url.value});const r=await fetch('/api/ollama/status?'+query),data=await r.json();$('ollamaState').textContent=data.message;$('ollamaDot').style.background=data.ready?'#25d7a1':'#ffcb4a'}catch{$('ollamaState').textContent='Não foi possível consultar o backend';$('ollamaDot').style.background='#ff8198'}setTimeout(checkOllama,10000)}
checkOllama();setInterval(refresh,1000);refresh();
</script></body></html>'''

# Estado local; somente um trabalho simultâneo por processo.
from .jobs import Pipeline, Cancelled
from .summary import matches
from flask import send_file
from collections import Counter
import threading
_cancel = threading.Event()

@app.get('/api/review')
def review_list():
    try:return jsonify(items=pending_review(Path(request.args.get('work','./workspace')).expanduser().resolve()))
    except (OSError,ValueError) as exc:return jsonify(error=str(exc)),400

@app.get('/api/review/report.csv')
def review_report_csv():
    from .review_csv import report_csv
    try:
        work = Path(request.args.get('work', './workspace')).expanduser().resolve()
        csv_content = report_csv(work)
        return Response(csv_content.encode('utf-8'), mimetype='text/csv',
                        headers={'Content-Disposition': 'attachment; filename="relatorio-revisao-humana.csv"',
                                 'Cache-Control': 'no-store'})
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return jsonify(error=str(exc)), 400

@app.post('/api/review/decision')
def review_decision():
    with _lock:
        if _state["status"]=="running":return jsonify(error="Aguarde o processamento terminar"),409
    data=request.get_json(silent=True) or {}
    try:
        item=record_decision(Path(data["work"]).expanduser().resolve(),str(data["file"]),str(data["key"]),str(data.get("translation","")),str(data["action"]))
        return jsonify(saved=True,item=item)
    except (ValueError,OSError,KeyError,TypeError) as exc:return jsonify(error=str(exc)),400

_instruction_lock=threading.Lock()
_instruction_state={'status':'idle','progress':0,'total':0,'result':None,'error':None}

@app.get('/api/review/instruction-status')
def instruction_status():
    with _instruction_lock:
        return jsonify(dict(_instruction_state))

@app.post('/api/review/instruct')
def instruction_start():
    with _lock:
        if _state['status']=='running':
            return jsonify(error='Conclua a execução atual antes da revisão'),409
    data=request.get_json(silent=True) or {}
    work=Path(str(data.get('work','./workspace'))).expanduser().resolve()
    file=str(data.get('file',''))
    instruction=str(data.get('instruction','')).strip()
    if not file or not instruction or len(instruction)>1200:
        return jsonify(error='Arquivo e instrução (até 1200 caracteres) são obrigatórios'),400
    with _instruction_lock:
        if _instruction_state['status']=='running':
            return jsonify(error='Já existe revisão por LLM em andamento'),409
        _instruction_state.update(status='running',progress=0,total=0,result=None,error=None)
    def task_instruction():
        try:
            from .review_instructions import instruct
            def progress(done,total,item):
                with _instruction_lock:
                    _instruction_state.update(progress=done,total=total,last=item)
            result=instruct(work,file,instruction,model=str(data.get('model','gemma3:4b')),
                           url=str(data.get('url','http://127.0.0.1:11434')),
                           key=data.get('key'),limit=int(data.get('limit',20)),on_progress=progress)
            with _instruction_lock:
                _instruction_state.update(status='done',result=result)
        except Exception as exc:
            with _instruction_lock:
                _instruction_state.update(status='error',error=str(exc))
    threading.Thread(target=task_instruction,daemon=True).start()
    return jsonify(started=True),202

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
def health():return jsonify(service='Aray Zomboid Translator',version='0.9.1',ok=True)

@app.get('/api/ollama/status')
def ollama_status():
    from .ollama import OllamaClient
    try:
        client = OllamaClient(request.args.get('url', 'http://127.0.0.1:11434'),
                              request.args.get('model', 'gemma3:4b'), timeout=2)
        return jsonify(client.health())
    except ValueError as exc:
        return jsonify(status='invalid_config', online=False, ready=False, message=str(exc)), 400

@app.get("/")
def index(): return render_template_string(HTML)

@app.get("/api/status")
def status():
    with _lock:return jsonify(dict(_state))

@app.get('/api/events')
def events():
    def stream():
        seen=-1
        last_sent=0.0
        while True:
            with _changed:
                if seen==_revision:
                    _changed.wait(timeout=15)
                # Coalesce rapid stage updates; never hold the lock while writing
                # to the client. Reconnection always receives the latest snapshot.
                wait=.1-(time.monotonic()-last_sent)
                while wait>0:
                    _changed.wait(timeout=wait)
                    wait=.1-(time.monotonic()-last_sent)
                if seen==_revision:
                    payload=': keepalive\n\n'
                else:
                    seen=_revision
                    payload=f'id: {seen}\nevent: status\ndata: '+json.dumps(dict(_state),ensure_ascii=False)+'\n\n'
                last_sent=time.monotonic()
            yield payload
    return Response(stream(),mimetype='text/event-stream',headers={
        'Cache-Control':'no-cache, no-transform','X-Accel-Buffering':'no'})

@app.post("/api/start")
def start():
    data = request.get_json(silent=True) or {}
    if not isinstance(data,dict): return jsonify(error="JSON inválido"),400
    with _lock:
        if _state["status"] == "running":return jsonify(error="Já existe uma execução ativa"),409
        run_id=uuid.uuid4().hex
        _publish(status="running",run_id=run_id,progress=0,percent=0,total=0,errors=0,result=None,message="Inicializando",summary=None,phase="starting",accepted=0,needs_review=0,reused=0,cancelled_count=0,remaining=0,workers=1,agent_events=[],agent_recent=[],active_workers=[],agent_queues={},manager_decisions={})
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
        with _lock:_publish(status="error",message=str(exc))
        return jsonify(error=str(exc)),400
    def task():
        try:
            filters = str(data.get('files','')).strip()
            limit=int(data.get('limit',0) or 0)
            workers=int(data.get('workers',1) or 1)
            def event(**kw):
                with _lock:
                    if _state.get('run_id')==run_id:
                        _publish(**kw)
            result=Pipeline(event,_cancel).run(*args[:7],files=filters,limit=limit,workers=workers)
            report=json.loads(Path(result['audit']).read_text(encoding='utf-8'))
            summary=summarize(report,filters,result['selected'])
            with _lock:_publish(status='error' if result.get('export_error') else ('partial' if result.get('blocked_files') else ('cancelled' if result.get('cancelled') else 'done')),result=result,summary=summary,message=result.get('export_error') or 'Concluído')
        except Exception as exc:
            with _lock:_publish(status='error',active_workers=[],agent_queues={},message=f'{type(exc).__name__}: {exc}')
    Thread(target=task,daemon=True).start()
    return jsonify(started=True),202
