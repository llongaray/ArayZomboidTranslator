import {useEffect, useState, type FormEvent} from 'react';
import {Activity, ArrowDownToLine, ArrowRight, BookOpen, Check, ChevronDown, CircleHelp, ClipboardCheck, FolderOpen, Layers3, LoaderCircle, Play, RefreshCw, Settings2, ShieldCheck, Square, Terminal, Wifi, WifiOff, X} from 'lucide-react';
import {motion, useReducedMotion} from 'motion/react';
import AgentRobot from './AgentRobot';
import ReviewByFile from './ReviewByFile';
import {post, api, usePoll} from './api';
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
  {id: 'translator', name: 'Tradutor', detail: 'Tradução com Ollama', color: '#7bb8f2'},
  {id: 'supervisor', name: 'Supervisor', detail: 'Validação e qualidade', color: '#72c7ad'},
  {id: 'manager', name: 'Gerente', detail: 'Decisão e correções', color: '#e6bc68'},
  {id: 'delivery', name: 'Entrega', detail: 'Exportação validada', color: '#a9c780'},
];
export default function App() {
  const [config, setConfig] = useState(readConfig);
  const [tab, setTab] = useState('overview');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [cancelRequested, setCancelRequested] = useState(false);
  const job = usePoll<JobState>('/api/status', 1200);
  const health = usePoll<OllamaState>('/api/ollama/status?model=' + encodeURIComponent(config.model), 10000);
  const s = job.data || {};
  const running = s.status === 'running';
  const offline = Boolean(job.error);
  const busy = running || submitting;
  const reduced = useReducedMotion();
  const active = running ? s.active_workers || [] : [];
  const translators = active.filter(w => w.agent === 'translator').length;
  const auditDone = s.status === 'done' && s.phase === 'audit_done';
  const pct = auditDone ? 100 : s.total ? Math.max(0, Math.min(100, 100 * (s.progress || 0) / s.total)) : s.status === 'done' ? 100 : 0;
  const [events, setEvents] = useState<{message: string; time: string}[]>([]);
  useEffect(() => {try {localStorage.setItem('arayzt.config.v1', JSON.stringify(config))} catch { /* Storage may be disabled. */ }}, [config]);
  useEffect(() => {
    if (s.message) setEvents(old => old[0]?.message === s.message ? old : [{message: s.message!, time: new Date().toLocaleTimeString('pt-BR')}, ...old].slice(0, 40));
  }, [s.message]);
  useEffect(() => {if (!running) setCancelRequested(false)}, [running]);
  function field<K extends keyof Config>(key: K, value: Config[K]) {setConfig(old => ({...old, [key]: value}))}
  async function start(event: FormEvent) {
    event.preventDefault(); setError(''); setSubmitting(true);
    try {await post('/api/start', {...config, batch: 1, url: 'http://127.0.0.1:11434'}); setTab('overview')}
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
      <a className="brand" href="#content" aria-label="Aray Zomboid Translator, início"><span className="brand-icon"><BookOpen size={23}/></span><span><strong>Aray <b>Zomboid</b> Translator</strong><small>Central de tradução <span className="version">v0.10.1</span></small></span></a>
      <div className="header-status"><span className={'connection ' + (offline ? 'bad' : job.data ? 'good' : '')}>{offline ? <WifiOff size={14}/> : <Wifi size={14}/>} {offline ? 'Backend desconectado' : job.data ? 'Backend conectado' : 'Conectando…'}</span><span className="local-label">EN <ArrowRight size={13}/> PT-BR</span></div>
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
              <label>Operação<select value={config.operation} onChange={e => field('operation', e.target.value)}><option value="audit">Auditar arquivos</option><option value="translate">Traduzir e exportar</option></select></label>
              <label>Escopo da auditoria<select value={config.mode} onChange={e => field('mode', e.target.value)}><option value="all">Todas as entradas elegíveis</option><option value="missing">Somente ausentes</option><option value="review">Entradas para revisão</option></select></label>
              <label>Grupos de arquivos<input value={config.files} onChange={e => field('files', e.target.value)} placeholder="Ex.: UI, ContextMenu, Moodles"/><small>Deixe vazio para incluir todos os grupos elegíveis.</small></label>
              <details className="advanced"><summary>Ajustes de tradução <ChevronDown size={14}/></summary><div className="advanced-body">
                <label>Modelo Ollama<input required value={config.model} onChange={e => field('model', e.target.value)} list="ollama-models"/><datalist id="ollama-models">{health.data?.models?.map(name => <option key={name} value={name}/>)}</datalist></label>
                <div className="field-pair"><label>Tradutores<select value={config.workers} onChange={e => field('workers', Number(e.target.value))}>{[1, 2, 3, 4].map(n => <option key={n} value={n}>{n} worker{n > 1 ? 's' : ''}</option>)}</select></label><label>Limite de entradas<input type="number" required min="0" step="1" value={config.limit} onChange={e => field('limit', Number(e.target.value))}/></label></div><small>Limite 0 processa todas as entradas selecionadas.</small>
              </div></details>
            </fieldset>
            <div className={'ollama-card ' + (health.data?.ready && !health.error ? 'good' : 'warn')} role="status"><span className="status-dot"/><div><strong>{health.error ? 'Diagnóstico indisponível' : health.data?.ready ? 'Ollama disponível' : health.data?.online ? 'Modelo não instalado' : health.data ? 'Ollama indisponível' : 'Verificando Ollama…'}</strong><small>{health.error || (health.data?.ready ? config.model + ' · ' + health.data.latency_ms + ' ms' : health.data?.message || 'Consultando o serviço local')}</small></div></div>
            <button className="primary start-button" type="submit" disabled={busy || offline || !config.game.trim() || !config.work.trim()}>{submitting ? <LoaderCircle className="spin" size={17}/> : <Play size={16}/>} {submitting ? 'Iniciando…' : config.operation === 'audit' ? 'Iniciar auditoria' : 'Traduzir e exportar'}<ArrowRight size={16}/></button>
            {running && <button className="danger full" type="button" disabled={cancelRequested} onClick={cancel}><Square size={14}/>{cancelRequested ? 'Cancelamento solicitado…' : 'Cancelar execução'}</button>}
            <p className="safe-note"><ShieldCheck size={15}/> A exportação é salva no workspace, separada dos arquivos do jogo.</p>
          </form>
        </aside>
        <div className="workspace-main">
          <nav className="tab-bar" aria-label="Seções do workspace">{[{id: 'overview', label: 'Visão geral', icon: Activity}, {id: 'review', label: 'Revisão humana', icon: ClipboardCheck}, {id: 'delivery', label: 'Entrega', icon: ArrowDownToLine}].map(({id, label, icon: Icon}) => <button key={id} aria-current={tab === id ? 'page' : undefined} onClick={() => setTab(id)}><Icon size={16}/>{label}{id === 'review' && Boolean(s.needs_review) && <span className="count-badge">{format(s.needs_review)}</span>}</button>)}</nav>
          {tab === 'overview' && <>
            <section className="panel overview"><div className="overview-top"><div><span className={'status-label ' + (s.status === 'error' ? 'bad' : running ? 'warn' : 'good')}><span className="status-dot"/>{labels[s.status || 'idle'] || s.status}</span><h2>{running ? labels[s.phase || ''] || 'Processando entradas' : s.status === 'done' ? 'Execução concluída' : s.status === 'cancelled' ? 'Execução cancelada' : s.status === 'error' ? 'A execução precisa de atenção' : s.status === 'partial' ? 'Alguns arquivos precisam de revisão' : 'Seu próximo mundo, em português.'}</h2><p>{s.message || 'Configure a execução ao lado. Comece com uma auditoria para conhecer os arquivos.'}</p></div><div className="progress-number">{pct.toFixed(1).replace('.', ',')}<span>%</span></div></div>
              <div className="track" role="progressbar" aria-label="Progresso da execução" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(pct)}><motion.div animate={{width: pct + '%'}} transition={{duration: reduced ? 0 : .4}}/></div><div className="progress-caption"><span>{auditDone ? 'Auditoria concluída' : <>{format(s.progress)} <span className="muted">de {format(s.total)} entradas processadas</span></>}</span><span>{running ? 'Atualização automática' : 'Pronto para uma nova execução'}</span></div>
            </section>
            <section className="metrics" aria-label="Resultados da execução">{[{label: 'Aprovadas', value: s.accepted, icon: Check, color: 'green'}, {label: 'Revisão humana', value: s.needs_review, icon: ClipboardCheck, color: 'amber'}, {label: 'Falhas', value: s.errors, icon: CircleHelp, color: 'red'}, {label: 'Selecionadas', value: s.total, icon: Layers3, color: 'blue'}].map(({label, value, icon: Icon, color}) => <div className={'metric ' + color} key={label}><div className="metric-label"><span>{label}</span><Icon size={16}/></div><strong>{format(value)}</strong><small>{label === 'Selecionadas' ? 'Nesta execução' : 'Entradas'}</small></div>)}</section>
            <section className="panel pipeline-panel"><div className="section-head"><div><h2>Equipe em campo</h2><p>Cada etapa cuida de uma parte da tradução.</p></div><span className="pill">{translators}/{s.workers || config.workers} tradutores ativos</span></div>
              <div className="robot-pipeline">{agents.map(agent => {const count = active.filter(w => w.agent === agent.id).length; const working = running && (count > 0 || agent.id === 'orchestrator' || agent.id === 'delivery' && s.phase === 'export'); return <AgentRobot key={agent.id} name={agent.name} color={agent.color} status={working ? 'working' : s.status === 'done' && s.result?.files !== undefined ? 'done' : 'waiting'} count={count} detail={agent.detail} workers={count} queued={running ? (s.agent_queues?.[agent.id] ?? 0) : 0} tasks={active.filter(w=>w.agent===agent.id).map(w=>({key:w.key,cycle:w.cycle}))}/>})}</div>
              <div className="pipeline-foot"><RefreshCw size={14}/><span>Entradas que precisam de correção retornam ao tradutor com feedback.</span></div>
              {active.length > 0 && <div className="worker-list">{active.map(w => <div key={w.worker}><span className="status-dot"/><strong>{labels[w.agent] || w.agent}</strong><span className="mono">{w.key}</span><small>Ciclo {w.cycle}</small></div>)}</div>}
            </section>
            <div className="data-grid"><section className="panel history-panel"><div className="section-head"><h2>Histórico das entradas</h2><span className="subtle">Últimas {s.agent_recent?.length || 0}</span></div><div className="table-scroll"><table><thead><tr><th scope="col">Arquivo / chave</th><th scope="col">Ciclos</th><th scope="col">Resultado</th></tr></thead><tbody>{s.agent_recent?.slice().reverse().map(item => <tr key={item.file + item.key}><td><strong>{item.file}</strong><span className="mono">{item.key}</span></td><td>{item.history.filter(h => h.agent === 'translator').length}</td><td><span className={'result-tag ' + item.status}>{labels[item.status] || item.status}</span></td></tr>)}</tbody></table></div>{!s.agent_recent?.length && <Empty icon={<Layers3 size={25}/>} title="Nenhuma entrada processada" text="O histórico aparece aqui quando a tradução começar."/>}</section>
              <section className="panel"><div className="section-head"><h2>Cobertura original</h2><BookOpen size={17} className="muted"/></div><div className="coverage-number">{s.summary?.total ? Math.round(100 * (counts.translated || 0) / s.summary.total) : 0}<span>%</span><small>das entradas já traduzidas</small></div><div className="coverage"><div style={{width: (s.summary?.total ? 100 * (counts.translated || 0) / s.summary.total : 0) + '%'}}/></div><div className="coverage-legend">{[{key: 'translated', label: 'Traduzidas'}, {key: 'missing', label: 'Ausentes'}, {key: 'identical', label: 'Idênticas'}, {key: 'placeholder_mismatch', label: 'Placeholders divergentes'}].map(item => <div key={item.key}><span>{item.label}</span><strong>{format(counts[item.key])}</strong></div>)}</div><p className="subtle">Referência da última auditoria dos arquivos do jogo.</p></section></div>
            <section className="panel activity-panel"><div className="section-head"><h2><Terminal size={16}/> Atividade recente</h2><span className="subtle">Nesta sessão</span></div>{events.length ? <div className="logs">{events.map((event, i) => <div className="log" key={event.time + i}><time>{event.time}</time><span>{event.message}</span></div>)}</div> : <p className="subtle">Nenhum evento ainda. Tudo pronto para começar.</p>}</section>
          </>}
          {tab === 'review' && <ReviewWorkspace work={config.work} model={config.model} running={running}/>}
          {tab === 'delivery' && <section className="panel delivery-panel"><div className="section-head"><div><h2>Entrega e arquivos</h2><p>Resultados disponíveis no workspace da execução.</p></div><ArrowDownToLine size={22}/></div>{s.result && (s.result.files !== undefined || s.result.export_error) ? <><div className="delivery-summary"><strong>{format(s.result.files)}</strong><span>arquivo(s) exportado(s)</span></div>{s.result.export_error && <div className="notice error" role="alert">{s.result.export_error}</div>}<label>Pasta de saída<div className="file-path mono">{s.result.output || 'Nenhuma pasta de saída informada.'}</div></label>{s.result.blocked_files?.map((file, i) => <details className="blocked-file" key={file.file || i}><summary>{file.file || 'Arquivo desconhecido'} · bloqueado</summary><pre>{JSON.stringify(file.issues, null, 2)}</pre></details>)}<details className="advanced"><summary>Detalhes da exportação <ChevronDown size={14}/></summary><pre>{JSON.stringify(s.result, null, 2)}</pre></details></> : <Empty icon={<FolderOpen size={32}/>} title="Sua entrega aparecerá aqui" text="Execute uma tradução para gerar os arquivos. Somente entradas validadas são exportadas."/>}</section>}
        </div>
      </div><footer>Aray Zomboid Translator <span>Tradução local · Inglês → Português brasileiro</span></footer>
    </main>
  </>;
}
function Empty({icon, title, text}: {icon: React.ReactNode; title: string; text: string}) {return <div className="empty"><div>{icon}</div><strong>{title}</strong><p>{text}</p></div>}
function ReviewWorkspace({work, model, running}: {work: string; model: string; running: boolean}) {
  const [reviews, setReviews] = useState<ReviewItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  useEffect(() => {setReviews([]); setLoaded(false)}, [work]);
  async function load() {
    setLoading(true); setError('');
    try {const data = await api<{items: ReviewItem[]}>('/api/review?work=' + encodeURIComponent(work)); setReviews(data.items); setLoaded(true)}
    catch (e) {setError(e instanceof Error ? e.message : 'Erro ao carregar pendências.')}
    finally {setLoading(false)}
  }
  const visible = reviews.filter(r => (r.file + r.key + r.english).toLocaleLowerCase().includes(search.toLocaleLowerCase()));
  return <section className="panel"><div className="section-head"><div><h2>Revisão humana</h2><p>Confira traduções e oriente as próximas correções.</p></div><button className="secondary" disabled={loading || running} onClick={load}><RefreshCw size={15} className={loading ? 'spin' : ''}/>{loading ? 'Carregando…' : 'Carregar pendências'}</button></div>{running && <p className="warning">Aguarde a execução terminar para revisar.</p>}{error && <div className="notice error" role="alert">{error}</div>}{reviews.length > 0 ? <><ReviewByFile reviews={reviews} work={work} model={model} onRefresh={load} disabled={running}/><label className="review-search">Buscar pendências<input value={search} onChange={e => setSearch(e.target.value)} placeholder="Arquivo, chave ou texto original"/></label><p className="subtle">{visible.length} de {reviews.length} pendências</p>{visible.map(item => <Review key={work + item.file + item.key + item.translation} item={item} work={work} disabled={running}/>)}</> : <Empty icon={<ClipboardCheck size={30}/>} title={loaded ? 'Nenhuma revisão pendente' : 'Uma segunda leitura faz a diferença'} text={loaded ? 'Não há pendências neste workspace.' : 'Carregue as pendências do workspace para conferir e aprovar cada tradução.'}/>}</section>;
}
function Review({item, work, disabled}: {item: ReviewItem; work: string; disabled: boolean}) {
  const [value, setValue] = useState(item.translation || '');
  const [feedback, setFeedback] = useState('');
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  async function decide(action: 'approve' | 'reject') {
    setBusy(true); setFeedback('');
    try {await post('/api/review/decision', {work, file: item.file, key: item.key, translation: value, action}); setSaved(true); setFeedback(action === 'approve' ? 'Aprovação registrada. Execute novamente para exportar.' : 'Rejeição registrada.')}
    catch (e) {setFeedback(e instanceof Error ? e.message : 'Erro ao salvar.')}
    finally {setBusy(false)}
  }
  return <article className="reviewItem"><small className="subtle">{item.file}</small><h3 className="mono">{item.key}</h3><p className="source-text">{item.english || '(Fonte vazia)'}</p>{item.reasons?.length ? <p className="warning">{item.reasons.join(' · ')}</p> : null}<label>Tradução em português<textarea value={value} disabled={disabled || busy || saved} onChange={e => setValue(e.target.value)} rows={3}/></label><div className="actions"><button disabled={disabled || busy || saved || !value.trim()} onClick={() => decide('approve')}><Check size={15}/> Aprovar</button><button className="secondary" disabled={disabled || busy || saved} onClick={() => decide('reject')}>Rejeitar</button></div>{feedback && <p role="status">{feedback}</p>}</article>;
}
