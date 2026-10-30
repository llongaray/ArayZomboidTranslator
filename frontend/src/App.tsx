import {useEffect, useState, type FormEvent} from 'react';
import {Activity, ArrowDownToLine, ArrowRight, BookOpen, Check, ChevronDown, CircleHelp, ClipboardCheck, FolderOpen, Layers3, LoaderCircle, Play, RefreshCw, Settings2, ShieldCheck, Square, Terminal, Wifi, WifiOff, X} from 'lucide-react';
import {motion, useReducedMotion} from 'motion/react';
import AgentRobot from './AgentRobot';
import {post, api, usePoll, useLiveStatus} from './api';
import {defaults, format, labels, type Config, type JobState, type OllamaState, type ReviewItem} from './types';

function readConfig(): Config {
  try {
    const saved = JSON.parse(localStorage.getItem('arayzt.config.v1') || '{}');
    const config = {...defaults};
    for (const key of Object.keys(defaults) as (keyof Config)[]) {
      if (typeof saved[key] === typeof defaults[key]) Object.assign(config, {[key]: saved[key]});
    }
    return config;
  } catch { return defaults }
}
const agents = [
  {id: 'orchestrator', name: 'Orquestrador', detail: 'Distribuição de tarefas', color: '#b6a0ed'},
  {id: 'translator', name: 'Tradutor I', detail: 'Novas traduções', color: '#7bb8f2'},
  {id: 'translator_ii', name: 'Tradutor II', detail: 'Correções solicitadas', color: '#70acff'},
  {id: 'supervisor', name: 'Supervisor', detail: 'Validação e qualidade', color: '#72c7ad'},
  {id: 'manager', name: 'Gerente', detail: 'Decisão e correções', color: '#e6bc68'},
  {id: 'analyst', name: 'Analista', detail: 'Worker 5 · tradução local', color: '#db9dd1'},
];
export default function App() {
  const [config, setConfig] = useState(readConfig);
  const [tab, setTab] = useState('overview');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [cancelRequested, setCancelRequested] = useState(false);
  const job = useLiveStatus<JobState>();
  const health = usePoll<OllamaState>('/api/ollama/status?model=' + encodeURIComponent(config.model), 10000);
  const analystHealth=usePoll<{ready:boolean;provider:string}>('/api/analyst/status',15000);
  const snapshot=job.data||{};
  const s=(snapshot.status==='done' && (snapshot.delivery_status==='partial'||snapshot.result?.delivery_status==='partial')) ? {...snapshot,status:'partial'} : snapshot;
  const running = s.status === 'running';
  const offline = Boolean(job.error);
  const busy = running || submitting;
  const reduced = useReducedMotion();
  const active = running ? s.active_workers || [] : [];
  const translators = active.filter(w => w.agent === 'translator').length;
  const retranslator = active.filter(w => w.agent === 'translator_ii').length;
  const auditDone = s.status === 'done' && s.phase === 'audit_done';
  const pct = auditDone ? 100 : s.percent !== undefined ? Math.max(0,Math.min(100,s.percent)) : s.total ? Math.max(0, Math.min(100, 100 * (s.progress || 0) / s.total)) : s.status === 'done' ? 100 : 0;
  const [events, setEvents] = useState<{message: string; time: string}[]>([]);
  useEffect(() => {try {localStorage.setItem('arayzt.config.v1', JSON.stringify(config))} catch { /* Storage may be disabled. */ }}, [config]);
  useEffect(() => {
    if (s.message) setEvents(old => old[0]?.message === s.message ? old : [{message: s.message!, time: new Date().toLocaleTimeString('pt-BR')}, ...old].slice(0, 40));
  }, [s.message]);
  useEffect(() => {if (!running) setCancelRequested(false)}, [running]);
  function field<K extends keyof Config>(key: K, value: Config[K]) {setConfig(old => ({...old, [key]: value}))}
  async function start(event: FormEvent) {
    event.preventDefault(); setError(''); setSubmitting(true);
    try {await post('/api/start', {...config, url: 'http://127.0.0.1:11434'}); setTab('overview')}
    catch (e) {setError(e instanceof Error ? e.message : 'Não foi possível iniciar.')}
    finally {setSubmitting(false)}
  }
  async function cancel() {
    setError(''); setCancelRequested(true);
    try {await post('/api/cancel')} catch (e) {setCancelRequested(false); setError(e instanceof Error ? e.message : 'Não foi possível cancelar.')}
  }
  const counts = s.summary?.counts || {};
  return <>
    <a className="skip-link" href="#content">Ir para o conteúdo</a>
    <header className="header"><div className="header-inner">
      <a className="brand" href="#content" aria-label="Aray Zomboid Translator, início"><span className="brand-icon"><BookOpen size={23}/></span><span><strong>Aray <b>Zomboid</b> Translator</strong><small>Central de tradução <span className="version">v0.10.2</span></small></span></a>
      <div className="header-status"><span className={'connection ' + (offline ? 'bad' : job.data ? 'good' : '')}>{offline ? <WifiOff size={14}/> : <Wifi size={14}/>} {offline ? 'Backend desconectado' : job.data ? job.transport==='live' ? 'Conectado · tempo real' : 'Conectado · consulta periódica' : 'Conectando…'}</span><span className="local-label">EN <ArrowRight size={13}/> PT-BR</span></div>
    </div></header>
    <main className="shell" id="content">
      <div className="page-heading"><div><div className="eyebrow">PROJECT ZOMBOID · BUILD 42</div><h1>Do original ao <span>sobrevivente.</span></h1><p>Audite, traduza e revise os textos do jogo em um só lugar.</p></div><a className="text-link" href="#configuration"><Settings2 size={16}/> Configurar execução <ArrowRight size={14}/></a></div>
      {offline && <div className="notice error" role="alert"><WifiOff size={19}/><div><strong>Conexão com o backend interrompida</strong><p>{job.error} A reconexão é automática; os dados exibidos podem estar desatualizados.</p></div></div>}
      {error && <div className="notice error" role="alert"><CircleHelp size={19}/><span>{error}</span><button className="icon-button" onClick={() => setError('')} aria-label="Fechar aviso"><X size={16}/></button></div>}
      <div className="workspace-layout">
        <aside className="configuration panel" id="configuration">
          <div className="section-heading"><span className="section-icon"><Settings2 size={18}/></span><div><h2>Nova execução</h2><p>Prepare seu workspace</p></div></div>
          <form onSubmit={start}>
            <fieldset disabled={busy}>
              <label>Diretório do jogo <span className="required">*</span><div className="input-icon"><FolderOpen size={16}/><input required value={config.game} onChange={e => field('game', e.target.value)} placeholder="E:\Games\…\Translate" autoComplete="off"/></div></label>
              <label>Workspace<input required value={config.work} onChange={e => field('work', e.target.value)} autoComplete="off"/><small>Auditoria, checkpoint e arquivos exportados.</small></label>
              <div className="field-divider"/>
              <label>Operação<select value={config.operation} onChange={e => field('operation', e.target.value)}><option value="audit">Auditar arquivos</option><option value="translate">Traduzir e exportar</option><option value="export">Exportar checkpoint aprovado</option></select></label>
              <label>Escopo da auditoria<select value={config.mode} onChange={e => field('mode', e.target.value)}><option value="all">Todas as entradas elegíveis</option><option value="missing">Somente ausentes</option><option value="review">Entradas para revisão</option></select></label>
              <label>Grupos de arquivos<input value={config.files} onChange={e => field('files', e.target.value)} placeholder="Ex.: UI, ContextMenu, Moodles"/><small>Deixe vazio para incluir todos os grupos elegíveis.</small></label>
              <details className="advanced"><summary>Ajustes de tradução <ChevronDown size={14}/></summary><div className="advanced-body">
                <label>Modelo Ollama<input required value={config.model} onChange={e => field('model', e.target.value)} list="ollama-models"/><datalist id="ollama-models">{health.data?.models?.map(name => <option key={name} value={name}/>)}</datalist></label>
                <div className="field-pair"><label>Tradutores<select value={config.workers} onChange={e => field('workers', Number(e.target.value))}>{[1, 2, 3, 4].map(n => <option key={n} value={n}>{n} worker{n > 1 ? 's' : ''}</option>)}</select></label><label>Limite de entradas<input type="number" required min="0" step="1" value={config.limit} onChange={e => field('limit', Number(e.target.value))}/></label></div><label>Textos curtos por chamada<select value={config.batch} onChange={e=>field('batch',Number(e.target.value))}>{[1,2,4].map(n=><option key={n} value={n}>{n} texto{n>1?'s':''}</option>)}</select><small>Textos longos e correções são enviados individualmente.</small></label><small>Limite 0 processa todas as entradas selecionadas.</small>
              </div></details>
            </fieldset>
            <div className={'ollama-card ' + (health.data?.ready && !health.error ? 'good' : 'warn')} role="status"><span className="status-dot"/><div><strong>{health.error ? 'Diagnóstico indisponível' : health.data?.ready ? 'Ollama disponível' : health.data?.online ? 'Modelo não instalado' : health.data ? 'Ollama indisponível' : 'Verificando Ollama…'}</strong><small>{health.error || (health.data?.ready ? config.model + ' · ' + health.data.latency_ms + ' ms' : health.data?.message || 'Consultando o serviço local')}</small></div></div>
            <button className="primary start-button" type="submit" disabled={busy || offline || !config.game.trim() || !config.work.trim()}>{submitting ? <LoaderCircle className="spin" size={17}/> : <Play size={16}/>} {submitting ? 'Iniciando…' : config.operation === 'audit' ? 'Iniciar auditoria' : config.operation === 'export' ? 'Exportar checkpoint' : 'Traduzir e exportar'}<ArrowRight size={16}/></button>
            {running && <button className="danger full" type="button" disabled={cancelRequested} onClick={cancel}><Square size={14}/>{cancelRequested ? 'Cancelamento solicitado…' : 'Cancelar execução'}</button>}
            <p className="safe-note"><ShieldCheck size={15}/> A exportação é salva no workspace, separada dos arquivos do jogo.</p>
          </form>
        </aside>
        <div className="workspace-main">
          <nav className="tab-bar" aria-label="Seções do workspace">{[{id: 'overview', label: 'Visão geral', icon: Activity}, {id: 'review', label: 'Analista', icon: ClipboardCheck}, {id: 'delivery', label: 'Entrega', icon: ArrowDownToLine}].map(({id, label, icon: Icon}) => <button key={id} aria-current={tab === id ? 'page' : undefined} onClick={() => setTab(id)}><Icon size={16}/>{label}{id === 'review' && Boolean(s.analyst_pending) && <span className="count-badge">{format(s.analyst_pending)}</span>}</button>)}</nav>
          {tab === 'overview' && <>
            <section className="panel overview"><div className="overview-top"><div><span className={'status-label ' + (s.status === 'error' ? 'bad' : running ? 'warn' : 'good')}><span className="status-dot"/>{labels[s.status || 'idle'] || s.status}</span><h2>{running ? labels[s.phase || ''] || 'Processando entradas' : s.status === 'done' ? 'Execução concluída' : s.status === 'cancelled' ? 'Execução cancelada' : s.status === 'error' ? 'A execução precisa de atenção' : s.status === 'partial' ? 'Alguns arquivos precisam de revisão' : 'Seu próximo mundo, em português.'}</h2><p>{s.message || 'Configure a execução ao lado. Comece com uma auditoria para conhecer os arquivos.'}</p></div><div className="progress-number">{pct.toFixed(1).replace('.', ',')}<span>%</span></div></div>
              <div className="track" role="progressbar" aria-label="Progresso da execução" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(pct)}><motion.div animate={{width: pct + '%'}} transition={{duration: reduced ? 0 : .4}}/></div><div className="progress-caption"><span>{auditDone ? 'Auditoria concluída' : <>{format(s.progress)} <span className="muted">de {format(s.total)} entradas processadas</span></>}</span><span>{running ? job.transport==='live' ? 'Atualização em tempo real' : 'Consulta periódica' : 'Pronto para uma nova execução'}</span></div>
            </section>
            <section className="metrics" aria-label="Resultados da execução">{[{label: 'Aprovadas', value: s.accepted, icon: Check, color: 'green'}, {label: 'Exportadas', value: s.exported_entries ?? s.result?.exported_entries, icon: ArrowDownToLine, color: 'green'}, {label: 'Aprovadas sem exportar', value: s.approved_unexported ?? s.result?.approved_unexported ?? s.accepted, icon: ClipboardCheck, color: 'amber'}, {label: 'Arquivos bloqueados', value: s.blocked_file_count ?? s.result?.blocked_file_count, icon: ShieldCheck, color: 'red'}, {label: 'Analista', value: s.analyst_pending, icon: ClipboardCheck, color: 'amber'}, {label: 'Falhas', value: s.errors, icon: CircleHelp, color: 'red'}, {label: 'Selecionadas', value: s.total, icon: Layers3, color: 'blue'}].map(({label, value, icon: Icon, color}) => <div className={'metric ' + color} key={label}><div className="metric-label"><span>{label}</span><Icon size={16}/></div><strong>{format(value)}</strong><small>{label === 'Selecionadas' ? 'Nesta execução' : label === 'Arquivos bloqueados' ? 'Arquivos' : 'Entradas'}</small></div>)}</section>
            <section className="panel pipeline-panel"><div className="section-head"><div><h2>Equipe em campo</h2><p>Cada etapa cuida de uma parte da tradução.</p></div><span className="pill">{translators+retranslator}/{s.workers || config.workers} Ollama · Analista: {active.filter(w=>w.agent==='analyst').length}/1</span></div>
              {running && !s.agent_queues && <p className="notice error" role="status">O backend em execução não fornece filas e decisões. A atualização exige reiniciá-lo após salvar o checkpoint; zero não indica fila vazia.</p>}<div className="robot-pipeline">{agents.map(agent => {const count = active.filter(w => w.agent === agent.id).length; const working = running && (count > 0 || agent.id === 'orchestrator'); return <AgentRobot key={agent.id} name={agent.name} color={agent.color} status={working ? 'working' : s.status === 'done' && s.result?.files !== undefined ? 'done' : 'waiting'} count={count} detail={agent.detail} workers={count} queueLabel={agent.id==='orchestrator'?'Pendentes':'Na fila'} queued={running && s.phase==='translate' ? agent.id==='orchestrator' ? s.remaining ?? Math.max(0,(s.total||0)-(s.progress||0)) : s.agent_queues?.[agent.id] : 0} tasks={active.filter(w=>w.agent===agent.id).flatMap(w=>w.detail?.tasks||[{key:w.key,cycle:w.cycle}])}/>})}</div>
              <p className="subtle">Analista {analystHealth.data?.ready?'local disponível':'local indisponível'} · Pool compartilhado: Tradutor I cria traduções; Tradutor II atende correções solicitadas pelo gerente. {format(s.reused||0)} entradas reutilizadas do checkpoint/glossário; Pendências encaminhadas automaticamente ao analista.</p><div className="pipeline-foot"><RefreshCw size={14}/><span>Resultados registrados: {format((s.progress||0))}/{format(s.total||0)} · Gerente: {s.manager_decisions ? format(s.manager_decisions.approved||0) : '—'} aprovadas, {s.manager_decisions ? format(s.manager_decisions.analyze||0) : '—'} enviadas ao analista, {s.manager_decisions ? format(s.manager_decisions.rejected||0) : '—'} rejeitadas, {s.manager_decisions ? format(s.manager_decisions.retry||0) : '—'} retraduções solicitadas.</span></div>
              {active.length > 0 && <div className="worker-list">{active.map(w => <div key={w.worker}><span className="status-dot"/><strong>{labels[w.agent] || w.agent}</strong><span className="mono">{w.key}</span><small>Ciclo {w.cycle}</small></div>)}</div>}
              <div className="decision-log"><div className="section-head"><h3>Execução e decisões</h3><span className="subtle">Últimos {s.agent_events?.length || 0} eventos</span></div>{s.agent_events?.length ? <div className="table-scroll"><table><thead><tr><th scope="col">Horário / agente</th><th scope="col">Entrada</th><th scope="col">Decisão</th><th scope="col">Motivo</th></tr></thead><tbody>{s.agent_events.slice().reverse().map(event=><tr key={event.id}><td><time>{new Date(event.timestamp*1000).toLocaleTimeString('pt-BR')}</time><strong>{labels[event.agent]||event.agent}</strong></td><td><span className="mono">{event.key||'Pré-processamento'}</span><small className="subtle">{event.file}{event.cycle>0?' · ciclo '+event.cycle:''}</small></td><td><span className={'result-tag '+event.action}>{({started:'Em execução',done:'Feito',approved:'Aprovado',needs_review:'Analisar',rejected:'Reprovado',retry:'Refazer',analyze:'Enviar ao analista',cancelled:'Não feito · cancelado',reused:'Reutilizado',review_preserved:'Revisão preservada'} as Record<string,string>)[event.action]||event.action}</span></td><td className="decision-reason">{event.reasons.map(reason=>({supervisor_passed:'Validação aprovada',max_cycles:'Limite de tentativas',no_progress:'Resposta repetida; acionar analista',placeholder_mismatch:'Placeholders divergentes',suspected_english:'Possível texto em inglês',unchanged_english:'Original não traduzido',glossary_mismatch:'Divergência de glossário',structural_echo:'Identificador no lugar da tradução',cancelled:'Cancelamento solicitado'} as Record<string,string>)[reason]||reason).join(' · ')||'—'}</td></tr>)}</tbody></table></div>:<p className="subtle">As etapas e decisões serão registradas aqui, incluindo aprovações, reprovações, análises e pedidos de correção.</p>}</div>
            </section>
            <div className="data-grid"><section className="panel history-panel"><div className="section-head"><h2>Histórico das entradas</h2><span className="subtle">Últimas {s.agent_recent?.length || 0}</span></div><div className="table-scroll"><table><thead><tr><th scope="col">Arquivo / chave</th><th scope="col">Ciclos</th><th scope="col">Resultado</th></tr></thead><tbody>{s.agent_recent?.slice().reverse().map(item => <tr key={item.file + item.key}><td><strong>{item.file}</strong><span className="mono">{item.key}</span></td><td>{item.history.filter(h => h.agent === 'translator' || h.agent === 'translator_ii').length}</td><td><span className={'result-tag ' + item.status}>{labels[item.status] || item.status}</span></td></tr>)}</tbody></table></div>{!s.agent_recent?.length && <Empty icon={<Layers3 size={25}/>} title="Nenhuma entrada processada" text="O histórico aparece aqui quando a tradução começar."/>}</section>
              <section className="panel"><div className="section-head"><h2>Cobertura original</h2><BookOpen size={17} className="muted"/></div><div className="coverage-number">{s.summary?.total ? Math.round(100 * (counts.translated || 0) / s.summary.total) : 0}<span>%</span><small>das entradas já traduzidas</small></div><div className="coverage"><div style={{width: (s.summary?.total ? 100 * (counts.translated || 0) / s.summary.total : 0) + '%'}}/></div><div className="coverage-legend">{[{key: 'translated', label: 'Traduzidas'}, {key: 'missing', label: 'Ausentes'}, {key: 'identical', label: 'Idênticas'}, {key: 'placeholder_mismatch', label: 'Placeholders divergentes'}].map(item => <div key={item.key}><span>{item.label}</span><strong>{format(counts[item.key])}</strong></div>)}</div><p className="subtle">Referência da última auditoria dos arquivos do jogo.</p></section></div>
            <section className="panel activity-panel"><div className="section-head"><h2><Terminal size={16}/> Atividade recente</h2><span className="subtle">Nesta sessão</span></div>{events.length ? <div className="logs">{events.map((event, i) => <div className="log" key={event.time + i}><time>{event.time}</time><span>{event.message}</span></div>)}</div> : <p className="subtle">Nenhum evento ainda. Tudo pronto para começar.</p>}</section>
          </>}
          {tab === 'review' && <ReviewWorkspace work={config.work} running={running}/>}
          {tab === 'delivery' && <section className="panel delivery-panel"><div className="section-head"><div><h2>Entrega e arquivos</h2><p>Resultados disponíveis no workspace da execução.</p></div><ArrowDownToLine size={22}/></div>{s.result && (s.result.files !== undefined || s.result.export_error) ? <><div className="delivery-summary"><strong>{format(s.result.files)}</strong><span>arquivo(s) exportado(s)</span></div>{s.result.delivery_status==='partial' && <div className="notice error" role="status">Entrega parcial: existem aprovações ainda sem exportação validada.</div>}{s.result.export_error && <div className="notice error" role="alert">{s.result.export_error}</div>}<a className="text-link audit-download" href={'/api/delivery/audit.csv?work='+encodeURIComponent(config.work)} download="auditoria-traducao.csv"><ArrowDownToLine size={16}/> Baixar auditoria completa (antes/depois e responsável)</a><label>Pasta de saída<div className="file-path mono">{s.result.output || 'Nenhuma pasta de saída informada.'}</div></label>{s.result.blocked_files?.map((file, i) => <details className="blocked-file" key={file.file || i}><summary>{file.file || 'Arquivo desconhecido'} · bloqueado</summary><pre>{JSON.stringify(file.issues, null, 2)}</pre></details>)}<details className="advanced"><summary>Detalhes da exportação <ChevronDown size={14}/></summary><pre>{JSON.stringify(s.result, null, 2)}</pre></details></> : <Empty icon={<FolderOpen size={32}/>} title="Sua entrega aparecerá aqui" text="Execute uma tradução para gerar os arquivos. Somente entradas validadas são exportadas."/>}</section>}
        </div>
      </div><footer>Aray Zomboid Translator <span>Tradução local · Inglês → Português brasileiro</span></footer>
    </main>
  </>;
}
function Empty({icon, title, text}: {icon: React.ReactNode; title: string; text: string}) {return <div className="empty"><div>{icon}</div><strong>{title}</strong><p>{text}</p></div>}
function ReviewWorkspace({work, running}: {work: string; running: boolean}) {
  const report=usePoll<{items:(ReviewItem & {error?:string;producer?:string})[]}>('/api/analyst/report?work='+encodeURIComponent(work),running?3000:10000);
  const items=report.data?.items||[];
  return <section className="panel"><div className="section-head"><div><h2>Analista de tradução</h2><p>Resolução automática por contexto e tradução local. Falhas mantêm o motivo e a candidata para diagnóstico.</p></div><a className="text-link" href={'/api/delivery/audit.csv?work='+encodeURIComponent(work)} download><ArrowDownToLine size={16}/> Auditoria CSV</a></div>{report.error && <p role="alert">{report.error}</p>}{items.map(item=><article className="reviewItem" key={item.file+item.key}><small>{item.file}</small><h3 className="mono">{item.key}</h3><p className="source-text">{item.english}</p><p>{item.translation}</p><p className="warning">{item.error||item.reasons?.join(' · ')}</p></article>)}{!items.length && <Empty icon={<ClipboardCheck size={30}/>} title={running?'Analista acompanhando a execução':'Nenhuma falha de análise registrada'} text="As entradas sem solução passam pelo analista automaticamente. Não há fila de aprovação humana."/>}</section>;
}
