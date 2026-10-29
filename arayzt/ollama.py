"""Cliente Ollama com schema, marcadores protegidos e retries."""
import json
import time
import socket
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from urllib.parse import urlsplit
from .core import protect, restore, tokens
from .quality import GLOSSARY

class OllamaClient:
    def __init__(self, url="http://127.0.0.1:11434", model="gemma3:4b", timeout=35):
        self.url = url.rstrip("/")
        parsed = urlsplit(self.url)
        if (parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1', 'localhost', '::1')
                or parsed.username is not None or parsed.password is not None
                or parsed.path not in ('', '/') or parsed.query or parsed.fragment):
            raise ValueError("Por segurança, use Ollama local (localhost/127.0.0.1)")
        parsed.port  # Reject malformed ports before making a request.
        self.model = model
        self.timeout = timeout

    def health(self):
        """Read installed models without loading a model or generating tokens.

        A successful check confirms API reachability and model installation only;
        it does not guarantee enough memory or that inference will succeed.
        """
        started = time.monotonic()
        state = dict(url=self.url, model=self.model, online=False, ready=False,
                     status='offline', models=[], model_available=False)
        try:
            with urlopen(self.url + '/api/tags', timeout=self.timeout) as response:
                data = json.load(response)
            models = data['models']
            if not isinstance(models, list):
                raise ValueError('Lista de modelos inválida')
            names = sorted({m['name'] for m in models if isinstance(m, dict)
                            and isinstance(m.get('name'), str)})
            wanted = self.model if ':' in self.model else self.model + ':latest'
            available = any((name if ':' in name else name + ':latest') == wanted for name in names)
            state.update(online=True, ready=available, models=names,
                         model_available=available,
                         status='ready' if available else 'model_missing',
                         message='Ollama acessível; modelo instalado' if available
                         else f'Ollama acessível; modelo {self.model} não instalado')
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            state.update(message=f'Ollama indisponível: {exc}')
        except (ValueError, KeyError, TypeError) as exc:
            state.update(status='invalid_response', message=f'Resposta inválida do Ollama: {exc}')
        state['latency_ms'] = round((time.monotonic() - started) * 1000)
        return state

    def generate(self, records):
        protected, maps = {}, {}
        for r in records:
            value, mapping = protect(r["en"])
            protected[r["key_id"]] = value
            maps[r["key_id"]] = mapping
        schema = {"type":"object","properties":{"translations":{"type":"object","properties":{r["key_id"]:{"type":"string"} for r in records},"required":[r["key_id"] for r in records],"additionalProperties":False}},"required":["translations"],"additionalProperties":False}
        feedback=records[0].get("manager_feedback","") if len(records)==1 else ""
        previous=records[0].get("previous_translation","") if len(records)==1 else ""
        prompt = ("Traduza textos de interface do jogo Project Zomboid de inglês para português brasileiro natural. "
                  "Responda EXCLUSIVAMENTE no JSON requerido. Preserve integralmente símbolos especiais, marcadores ⟦AZT0000⟧, "
                  "nomes próprios, quebras, símbolos de formatação e significado. Não traduza chaves; use IDs como chaves. "
                  "Glossário: Bandage = bandagem; Bleeding = sangramento; Hunger = fome; Pain = dor; "
                  "Minor Bleeding = sangramento leve. Traduza verbos de menus no infinitivo; nunca repita inglês sem tradução. "
                  "Nunca retorne nomes de arquivos .txt, IDs, chaves ou metadados como tradução. "
                  "Produza um campo translations com exatamente os IDs do lote. "
                  "Glossário obrigatório: " + json.dumps(GLOSSARY,ensure_ascii=False) + ". Textos: " + json.dumps(protected,ensure_ascii=False) + (" GERENTE: "+feedback+" ANTERIOR: "+previous if feedback else ""))
        payload = {"model":self.model,"prompt":prompt,"stream":False,"format":schema,"options":{"temperature":0,"num_ctx":4096,"num_predict":768}}
        request = Request(self.url + "/api/generate", data=json.dumps(payload).encode(),headers={"Content-Type":"application/json"},method="POST")
        try:
            with urlopen(request, timeout=self.timeout) as response:
                result = json.load(response)
        except (HTTPError,URLError,TimeoutError,socket.timeout) as exc:
            raise RuntimeError(f"Falha ao acessar Ollama: {exc}") from exc
        try:
            raw = json.loads(result["response"])
            translations = raw.get("translations",raw)
            if not isinstance(translations,dict):raise ValueError("Campo translations não é um objeto")
            if len(records)==1 and records[0]["key_id"] not in translations:
                # Tolerate a single-key object under a different name, but never
                # accept metadata/file/key fields as a translation.
                values=[v for k,v in translations.items() if isinstance(v,str) and k not in ("file","key","source","model","status")]
                if len(values)==1:translations={records[0]["key_id"]:values[0]}
            output = []
            for r in records:
                key_id = r["key_id"]
                translated = restore(translations[key_id],maps[key_id])
                if tokens(r["en"]) != tokens(translated):
                    raise ValueError(f"Placeholders alterados em {key_id}")
                if not translated.strip(): raise ValueError(f"Tradução vazia em {key_id}")
                output.append({"file":r["file"],"key":r["key"],"translation":translated,"source":r["status"]})
            return output
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Resposta inválida do Ollama: {exc}") from exc


def translate_rows(client, rows, batch_size=8, retries=2, on_progress=None):
    accepted, failed = [], []
    for start in range(0,len(rows),batch_size):
        batch = [dict(r,key_id=f"k{start+i}") for i,r in enumerate(rows[start:start+batch_size])]
        for attempt in range(retries+1):
            try:
                accepted.extend(client.generate(batch))
                break
            except Exception as exc:
                if attempt >= retries:
                    failed.extend({"file":r["file"],"key":r["key"],"error":str(exc)} for r in batch)
                else: time.sleep(min(attempt+1,3))
        if on_progress: on_progress(min(start+len(batch),len(rows)),len(rows),len(failed))
    return accepted,failed
