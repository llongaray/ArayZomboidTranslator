import {useEffect,useMemo,useState} from 'react';
type Review={file:string;key:string;english:string;translation:string;decision?:string};
type Props={reviews:Review[];work:string;model:string;onRefresh:()=>void};
type State={status:string;progress:number;total:number;error?:string;result?:{approved:number;processed:number;remaining:number;items:{key:string;status:string;translation?:string;error?:string}[]}};
export default function ReviewByFile({reviews,work,model,onRefresh}:Props){
 const files=useMemo(()=>Array.from(new Set(reviews.map(r=>r.file))),[reviews]);
 const [file,setFile]=useState(''),[key,setKey]=useState(''),[instruction,setInstruction]=useState(''),[job,setJob]=useState<State>({status:'idle',progress:0,total:0}),[note,setNote]=useState('');
 const selected=files.includes(file)?file:files[0]||'';
 useEffect(()=>{let live=true;const check=()=>fetch('/api/review/instruction-status').then(r=>r.json()).then(x=>{if(live)setJob(x)}).catch(()=>{});check();const id=setInterval(check,1250);return()=>{live=false;clearInterval(id)}},[]);
 async function submit(){
   setNote('');
   const res=await fetch('/api/review/instruct',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({work,file:selected,key:key||undefined,instruction,model,limit:20})});
   const data=await res.json();if(!res.ok)setNote(data.error||'Erro ao enviar');else setNote('Instrução enviada ao Ollama. Resultados aprovados serão salvos para a próxima exportação.');
 }
 const busy=job.status==='running';
 return <div className="instruction-panel">
   <h3>Orientar o LLM por arquivo</h3><p className="muted">Descreva o resultado desejado. O Ollama retraduz as pendências e valida cada chave antes de registrar a decisão. Os arquivos do jogo não são modificados.</p>
   <div className="instruction-fields"><label>Arquivo<select value={selected} onChange={e=>{setFile(e.target.value);setKey('')}}><option value="">Selecione</option>{files.map(f=><option key={f} value={f}>{f}</option>)}</select></label>
   <label>Entrada<select value={key} onChange={e=>setKey(e.target.value)}><option value="">Todas as pendências do arquivo (até 20)</option>{reviews.filter(r=>r.file===selected).map(r=><option key={r.key} value={r.key}>{r.key}</option>)}</select></label></div>
   <label>Mensagem para o tradutor<textarea placeholder="Ex.: Na descrição da garrafa, manter apenas 'garrafa 90%', preservando as marcações do jogo." rows={3} maxLength={1200} value={instruction} onChange={e=>setInstruction(e.target.value)}/></label>
   <button disabled={busy||!selected||!instruction.trim()} onClick={submit}>Enviar instrução à IA</button>
   <button className="ghost" onClick={onRefresh}>Atualizar pendências</button>
   {note&&<p className="muted">{note}</p>}
   {busy&&<p className="muted">Traduzindo: {job.progress}/{job.total||'?'} · execução em segundo plano</p>}
   {job.status==='error'&&<p className="warning">{job.error}</p>}
   {job.status==='done'&&job.result&&<div className="muted"><strong>{job.result.approved}</strong> aprovadas de {job.result.processed} analisadas. Para gerar arquivos atualizados, execute novamente “Traduzir e exportar” com o mesmo workspace.{job.result.items.filter(i=>i.status!=='approved').slice(0,5).map(i=><p key={i.key}>{i.key}: {i.status} {i.error||''}</p>)}</div>}
 </div>;
}
