import {useEffect, useState} from 'react';

export async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(path, {...options, signal: options?.signal ?? AbortSignal.timeout(8000)}).catch((error: Error) => {
    throw new Error(error.name === 'AbortError' || error.name === 'TimeoutError'
      ? 'O backend demorou a responder. A consulta será repetida automaticamente.'
      : 'Não foi possível conectar ao backend. Confira o servidor Python na porta 8767.');
  });
  if (!response.headers.get('content-type')?.includes('application/json')) {
    if (response.status === 404) throw new Error('Rota indisponível. Reinicie o backend para carregar a versão atual.');
    throw new Error('O backend não retornou JSON. Confira se o servidor Python está ativo na porta 8767.');
  }
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || data.message || (response.status === 404
    ? 'Rota indisponível. Reinicie o backend para carregar a versão atual.' : `Falha na consulta (${response.status}).`));
  return data as T;
}
export function post<T>(path: string, body?: unknown) {
  return api<T>(path, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: body === undefined ? undefined : JSON.stringify(body)});
}
export function usePoll<T>(path: string, delay: number, enabled = true) {
  const [state, setState] = useState<{data?: T; error: string; checked?: Date}>({error: ''});
  useEffect(() => {
    if (!enabled) return;
    let disposed = false;
    let timer: ReturnType<typeof setTimeout>;
    let controller: AbortController;
    setState({error: ''});
    async function poll() {
      controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 8000);
      try {
        const data = await api<T>(path, {signal: controller.signal});
        if (!disposed) setState({data, error: '', checked: new Date()});
      } catch (error) {
        if (!disposed) setState(old => ({...old, error: error instanceof Error ? error.message : 'Não foi possível conectar ao backend.'}));
      } finally {
        clearTimeout(timeout);
        if (!disposed) timer = setTimeout(poll, delay);
      }
    }
    void poll();
    return () => {disposed = true; clearTimeout(timer); controller?.abort()};
  }, [path, delay, enabled]);
  return state;
}
