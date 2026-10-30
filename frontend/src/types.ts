export type History = {agent: string; cycle?: number};
export type Entry = {file: string; key: string; status: string; history: History[]};
export type ReviewItem = {file: string; key: string; english: string; translation: string; reasons?: string[]};
export type ActiveWorker = {worker: number; agent: string; cycle: number; file: string; key: string};
export type JobState = {
  status?: string; phase?: string; progress?: number; total?: number; accepted?: number;
  needs_review?: number; errors?: number; workers?: number; message?: string;
  active_workers?: ActiveWorker[]; agent_queues?: Record<string, number>; agent_recent?: Entry[];
  summary?: {total?: number; counts?: Record<string, number>};
  result?: {files?: number; output?: string; export_error?: string; blocked_files?: {file?: string; issues?: unknown[]}[]};
};
export type OllamaState = {ready: boolean; online: boolean; status: string; message: string; latency_ms?: number; models?: string[]};
export type Config = {game: string; work: string; model: string; workers: number; limit: number; files: string; mode: string; operation: string};
export const defaults: Config = {game: '', work: './workspace', model: 'gemma3:4b', workers: 1, limit: 0, files: '', mode: 'all', operation: 'audit'};
export const format = (value = 0) => value.toLocaleString('pt-BR');
export const labels: Record<string, string> = {idle: 'Aguardando', running: 'Em andamento', done: 'Concluído', partial: 'Entrega parcial', error: 'Erro na execução', cancelled: 'Cancelado', approved: 'Aprovada', needs_review: 'Revisão humana', rejected: 'Rejeitada', translator: 'Tradutor I', translator_ii: 'Tradutor II', supervisor: 'Supervisor', manager: 'Gerente', audit: 'Auditoria', audit_done: 'Auditoria concluída', translate: 'Tradução', export: 'Exportação', starting: 'Preparando', export_partial: 'Entrega parcial', export_failed: 'Falha na exportação'};
