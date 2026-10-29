import {motion,useReducedMotion} from 'motion/react';
type Props={name:string;color:string;status:'working'|'waiting'|'done';count:number;detail:string;workers:number};
export default function AgentRobot({name,color,status,count,detail,workers}:Props){
 const reduce=useReducedMotion(),working=status==='working';
 return <div className="bot-station" style={{'--bot-color':color} as React.CSSProperties}>
  <div className={'bot-status '+status}><span className="bot-dot"/>{status==='working'?'Trabalhando':status==='done'?'Finalizado':'Esperando'}{count>0&&<small> · {count}</small>}</div>
  <div className="bot-scene">
   <motion.svg viewBox="0 0 220 160" className="bot-svg" role="img" aria-label={name+' robô trabalhando em computador'} animate={working&&!reduce?{y:[0,-3,0]}:{y:0}} transition={{duration:2.4,repeat:working?Infinity:0,ease:'easeInOut'}}>
    <ellipse cx="111" cy="149" rx="92" ry="8" fill="#020c18" opacity=".5"/>
    <path d="M35 123 L188 123 L176 132 L46 132Z" fill="#3a4e66" stroke="#64849c" strokeWidth="2"/>
    <path d="M48 132 L48 150 M172 132 L172 150" stroke="#566c83" strokeWidth="7"/>
    <path d="M31 64 L105 64 L111 119 L43 119Z" fill="#1f364e" stroke="#7893ac" strokeWidth="3"/>
    <path d="M38 69 L99 69 L104 109 L46 109Z" fill="#102d45"/>
    <path d="M50 93 L57 85 L65 91 L73 76 L83 82 L94 73" stroke={color} strokeWidth="3" fill="none"/>
    <path d="M42 118 L112 118 L122 124 L36 124Z" fill="#7b91a2"/>
    <path d="M48 120 L102 120" stroke="#273f54" strokeWidth="3" strokeDasharray="5 4"/>
    <rect x="123" y="85" width="59" height="59" rx="16" fill="#53687a" stroke="#91a5b8" strokeWidth="3"/>
    <rect x="116" y="18" width="83" height="76" rx="15" fill="#596d79" stroke="#a8a998" strokeWidth="3"/>
    <path d="M155 16 L159 3 L170 3" stroke="#a5b8c5" strokeWidth="5" fill="none"/>
    <rect x="127" y="31" width="61" height="48" rx="7" fill="#94d9d8" stroke="#1d4254" strokeWidth="5"/>
    <motion.g animate={working&&!reduce?{opacity:[1,.45,1]}:{opacity:1}} transition={{repeat:Infinity,duration:3}}>
     <rect x="143" y="47" width="6" height="8" rx="2" fill="#1f344c"/><rect x="166" y="47" width="6" height="8" rx="2" fill="#1f344c"/>
    </motion.g>
    <path d="M150 62 Q158 71 169 62" fill="none" stroke="#234154" strokeWidth="4" strokeLinecap="round"/>
    <motion.g style={{transformOrigin:'130px 102px'}} animate={working&&!reduce?{rotate:[0,10,-6,0]}:{rotate:0}} transition={{duration:.9,repeat:Infinity}}>
     <path d="M131 99 L108 109 L93 113" fill="none" stroke="#8495a7" strokeWidth="12" strokeLinecap="round"/>
     <rect x="88" y="108" width="17" height="12" rx="4" fill="#a8b1b1"/>
    </motion.g>
    <path d="M181 99 L189 119 L169 125" fill="none" stroke="#8195a5" strokeWidth="11" strokeLinecap="round"/>
    <path d="M139 144 L139 155 M167 144 L167 155" stroke="#697e8f" strokeWidth="10" strokeLinecap="round"/>
    <rect x="116" y="107" width="50" height="9" rx="3" fill={color} opacity=".62"/>
    <motion.circle cx="194" cy="23" r="4" fill={color} animate={working&&!reduce?{opacity:[.1,1,.1],scale:[.7,1.4,.7]}:{opacity:.35}} transition={{duration:1.5,repeat:Infinity}}/>
   </motion.svg>
  </div>
  <div className="bot-caption"><strong>{name}</strong><span>{detail}</span>{workers>0&&<small>{workers} worker(s) neste estágio</small>}</div>
 </div>;
}
