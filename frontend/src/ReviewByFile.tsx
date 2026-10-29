import {useState} from 'react';
import {ChevronDown, Send} from 'lucide-react';
import {post, usePoll} from './api';
import type {ReviewItem} from './types';
type Props = {reviews: ReviewItem[]; work: string; model: string; onRefresh: () => void; disabled?: boolean};
type InstructionState = {status: string; progress: number; total: number; error?: string; result?: {approved: number; processed: number; items: {key: string; status: string; error?: string}[]}};
export default function ReviewByFile({reviews, work, model, onRefresh, disabled}: Props) {
  const files = Array.from(new Set(reviews.map(r => r.file)));
  const [file, setFile] = useState('');
  const [key, setKey] = useState('');
  const [instruction, setInstruction] = useState('');
  const [note, setNote] = useState('');
  const [sending, setSending] = useState(false);
  const job = usePoll<InstructionState>('/api/review/instruction-status', 2000);
  const selected = files.includes(file) ? file : files[0] || '';
  const busy = sending || job.data?.status === 'running';
  async function submit() {
    setNote(''); setSending(true);
    try {await post('/api/review/instruct', {work, file: selected, key: key || undefined, instruction, model, limit: 20}); setNote('Instrução enviada. Após a revisão, execute novamente para exportar as aprovações.')}
    catch (e) {setNote(e instanceof Error ? e.message : 'Não foi possível enviar a instrução.')}
    finally {setSending(false)}
  }
  return <details className="instruction-panel"><summary><span>Orientar o tradutor por arquivo</span><ChevronDown size={16}/></summary><div className="instruction-body"><p className="muted">Descreva uma correção para até 20 pendências do arquivo. Cada resultado passa pela validação.</p><fieldset disabled={disabled || busy}>
    <div className="instruction-fields"><label>Arquivo<select value={selected} onChange={e => {setFile(e.target.value); setKey('')}}>{files.map(f => <option key={f} value={f}>{f}</option>)}</select></label><label>Entrada<select value={key} onChange={e => setKey(e.target.value)}><option value="">Todas as pendências (até 20)</option>{reviews.filter(r => r.file === selected).map(r => <option key={r.key} value={r.key}>{r.key}</option>)}</select></label></div>
    <label>Instrução<textarea placeholder="Ex.: Use verbos no infinitivo nos comandos do menu." maxLength={1200} rows={3} value={instruction} onChange={e => setInstruction(e.target.value)}/></label></fieldset>
    <div className="actions"><button disabled={disabled || busy || !selected || !instruction.trim()} onClick={submit}><Send size={14}/>{busy ? 'Processando…' : 'Enviar instrução'}</button><button className="secondary" onClick={onRefresh}>Atualizar pendências</button></div>
    {note && <p role="status">{note}</p>}{job.error && <p className="warning" role="status">{job.error}</p>}
    {job.data?.status === 'running' && <p role="status">Analisando {job.data.progress} de {job.data.total || '…'} entradas.</p>}
    {job.data?.status === 'error' && <p className="warning" role="alert">{job.data.error}</p>}
    {job.data?.status === 'done' && job.data.result && <p role="status">{job.data.result.approved} aprovadas de {job.data.result.processed} analisadas. Atualize as pendências para conferir.</p>}
  </div></details>;
}
