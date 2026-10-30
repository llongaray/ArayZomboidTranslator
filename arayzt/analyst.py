"""Preset analyst with an offline Argos EN -> Brazilian Portuguese fallback."""
from __future__ import annotations
import os
import re
from pathlib import Path
from .core import TOKEN_RE
from .quality import GLOSSARY
from .source_rules import reviewed_unchanged
from .analyst_rules import resolution, POLICY_VERSION
from .validation import validate_candidate

MODEL_ROOT = Path(__file__).resolve().parent.parent / 'workspace' / 'analyst-models'


def configure_argos():
    # Keep model/cache files in the workspace and avoid competing with Ollama's GPU.
    os.environ.setdefault('ARGOS_PACKAGES_DIR', str(MODEL_ROOT))
    os.environ.setdefault('ARGOS_DEVICE_TYPE', 'cpu')
    for variable, folder in [('XDG_DATA_HOME','data'),('XDG_CONFIG_HOME','config'),('XDG_CACHE_HOME','cache')]:
        os.environ.setdefault(variable, str(MODEL_ROOT.parent / 'analyst-runtime' / folder))


class ArgosBackend:
    name = 'argos-en-pb'

    def __init__(self):
        configure_argos()
        import argostranslate.package
        import ctranslate2
        self.package = next((p for p in argostranslate.package.get_installed_packages()
                             if p.from_code == 'en' and p.to_code == 'pb'), None)
        if self.package is None:
            raise RuntimeError('Modelo Argos EN → PT-BR não instalado; execute python -m arayzt.analyst_setup')
        self.name='argos-en-pb:'+self.package.package_version
        # Use the package's tokenizer and inference engine directly. Visible
        # fragments are already delimited, so no sentence-model downloads occur.
        self.engine = ctranslate2.Translator(str(self.package.package_path / 'model'),
            device='cpu', compute_type='int8', inter_threads=1, intra_threads=2)

    def translate(self, text):
        if len(text) > 2000:
            raise ValueError('analyst_source_too_long')
        prefix = self.package.target_prefix
        result = self.engine.translate_batch([self.package.tokenizer.encode(text)],
            target_prefix=[[prefix]] if prefix else None, beam_size=4,
            replace_unknowns=True, length_penalty=.2, max_decoding_length=512)[0]
        if len(result.hypotheses[0]) >= 512:
            raise ValueError('analyst_output_limit')
        translated = self.package.tokenizer.decode(result.hypotheses[0])
        if prefix and translated.startswith(prefix):
            translated = translated[len(prefix):]
        return translated.strip()


class TranslationAnalyst:
    def __init__(self, backend_factory=ArgosBackend):
        self.backend_factory = backend_factory
        self.backend = None

    def analyze(self, row, previous='', reasons=()):
        source, key = row['en'], row['key']
        actions = []
        candidate = None
        provider = 'preset'
        rule = resolution(key, source)
        if rule:
            candidate = rule['translation']
            provider = 'context-rules:v'+str(POLICY_VERSION)
            actions.append(rule['category'])
        elif reviewed_unchanged(key, source):
            candidate = source
            actions.append('reviewed_source')
        elif source in GLOSSARY:
            candidate = GLOSSARY[source]
            actions.append('reviewed_glossary')
        elif re.match(r'(?i)^\s*k\d+\s*[-–—:|]', previous):
            repaired = re.sub(r'(?i)^\s*k\d+\s*[-–—:|]\s*', '', previous)
            if validate_candidate(source, repaired, key)[0] == 'approved':
                candidate = repaired
                actions.append('remove_internal_prefix')
        try:
            if candidate is None:
                if not source.strip():
                    raise ValueError('empty_source')
                provider=getattr(self.backend_factory,'name','argos-en-pb')
                if self.backend is None:
                    self.backend = self.backend_factory()
                provider = self.backend.name
                # Translate only visible fragments. Tokens/markup/newlines never
                # enter the engine, so it cannot drop or renumber them.
                boundary = re.compile(TOKEN_RE.pattern + r'|\r\n|\n|\r', re.I)
                pieces = []
                start = 0
                def visible(text):
                    if not any(ch.isalpha() for ch in text):
                        return text
                    match = re.fullmatch(r'(\s*)(.*?)(\s*)', text, re.S)
                    translated = self.backend.translate(match[2])
                    if not isinstance(translated, str) or not translated.strip():
                        raise ValueError('analyst_empty_translation')
                    # Short UI fragments are not standalone prose sentences.
                    # Do not inject the engine's terminal full stop before a
                    # protected placeholder or into a one-word UI label.
                    if (len(match[2].split())<=4 and not match[2].endswith(('.', '!', '?'))
                            and translated.endswith('.') and not translated.endswith('...')):
                        translated=translated[:-1]
                        actions.append('preserve_ui_terminal_punctuation')
                    return match[1] + translated.strip() + match[3]
                for token in boundary.finditer(source):
                    pieces.extend((visible(source[start:token.start()]), token.group()))
                    start = token.end()
                pieces.append(visible(source[start:]))
                candidate = ''.join(pieces)
                actions.append('offline_translation_with_protected_tokens')
            status, faults = validate_candidate(source, candidate, key)
            return {'translation': candidate, 'status': status, 'reasons': faults,
                    'provider': provider, 'actions': actions, 'policy_version': POLICY_VERSION, 'diagnosis': list(reasons)}
        except Exception as exc:
            return {'translation': previous, 'status': 'needs_review',
                    'reasons': list(dict.fromkeys([*reasons, 'analyst_failed:' + str(exc)[:200]])),
                    'provider': provider, 'actions': actions, 'policy_version': POLICY_VERSION, 'diagnosis': list(reasons)}
