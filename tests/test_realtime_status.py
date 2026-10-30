import json
import threading
import time

from arayzt import staged_pipeline, jobs, web


def test_four_worker_budget_is_shared_with_corrections(monkeypatch):
    barrier = threading.Barrier(4, timeout=3)
    lock = threading.Lock()
    occupied = 0
    maximum = 0
    events = []

    def generate(client, rows, **kwargs):
        nonlocal occupied, maximum
        with lock:
            occupied += 1
            maximum = max(maximum, occupied)
        try:
            # All four available workers must serve the correction queue.
            assert rows[0].get('manager_feedback')
            barrier.wait()
            return [{'translation': 'Corrigido'}], []
        finally:
            with lock:
                occupied -= 1

    monkeypatch.setattr(staged_pipeline, 'translate_rows', generate)
    monkeypatch.setattr(staged_pipeline, 'validate_candidate',
                        lambda en, value, key: ('approved', []) if value == 'Corrigido'
                        else ('rejected', ['placeholder_mismatch']))
    rows = [{'file': 'UI_PTBR.txt', 'key': f'UI_{i}', 'en': 'Source',
             'ptbr': 'Rascunho', 'status': 'placeholder_mismatch'} for i in range(4)]
    result = []
    staged_pipeline.orchestrate_pipeline(rows, 'http://127.0.0.1:11434', 'fake', 4,
        threading.Event(), result.append,
        lambda slot, row, stage, cycle, detail: events.append((slot, stage)))
    assert maximum == 4
    assert len(result) == 4
    assert all(item['status'] == 'approved' for item in result)
    assert {slot for slot, stage in events if stage == 'translator_ii'} == {1, 2, 3, 4}


def test_live_pipeline_reports_progress_queues_and_all_decisions(tmp_path, monkeypatch):
    game = tmp_path / 'Translate'
    (game / 'EN').mkdir(parents=True)
    (game / 'PTBR').mkdir()
    entries = {f'UI_TestLive_{letter}': f'English {letter}' for letter in 'ABCD'}
    (game / 'EN' / 'UI.json').write_text(json.dumps(entries), encoding='utf-8')
    calls = {}

    def generate(client, rows, **kwargs):
        key = rows[0]['key']
        calls[key] = calls.get(key, 0) + 1
        time.sleep(.005)
        return [{'translation': 'Bom' if key.endswith('A') or
                 key.endswith('B') and calls[key] > 1 else 'Bad'}], []

    def validate(en, value, key):
        if key.endswith('D'):
            return 'rejected', ['structural_echo']
        return ('approved', []) if value == 'Bom' else ('rejected', ['suspected_english'])

    monkeypatch.setattr(staged_pipeline, 'translate_rows', generate)
    monkeypatch.setattr(staged_pipeline, 'validate_candidate', validate)
    snapshots = []
    state = {}

    def event(**values):
        state.update(values)
        snapshots.append(json.loads(json.dumps(state)))

    jobs.Pipeline(event).run(game, tmp_path / 'work', translate=True, workers=4)
    assert state['progress'] == state['total'] == 4
    assert state['percent'] == 100
    assert state['accepted'] == 2
    assert state['needs_review'] == 1
    assert state['failed'] == 1
    assert state['remaining'] == 0
    assert state['manager_decisions'] == {'approved': 2, 'needs_review': 1, 'rejected': 1, 'retry': 3}
    assert len(state['agent_recent']) == 4
    assert any(s.get('agent_queues', {}).get('translator', 0) == 4 for s in snapshots)
    assert {25, 50, 75, 100}.issubset({s.get('percent') for s in snapshots})
    assert {'approved', 'needs_review', 'rejected', 'retry', 'done'}.issubset(
        {event['action'] for event in state['agent_events']})
    assert state['active_workers'] == []
    assert all(s.get('progress', 0) <= s.get('total', 0) for s in snapshots)


def test_sse_and_polling_deliver_the_same_latest_revision(monkeypatch):
    monkeypatch.setattr(web, '_state', {'status': 'running'})
    monkeypatch.setattr(web, '_revision', 0)
    client = web.app.test_client()
    response = client.get('/api/events', buffered=False)
    try:
        assert response.mimetype == 'text/event-stream'
        assert b'event: status' in next(response.response)
        web._publish(progress=3, total=4, percent=75, failed=1,
                     agent_queues={'translator': 1, 'translator_ii': 2})
        payload = next(response.response).decode()
        streamed = json.loads(payload.split('data: ', 1)[1])
        polled = client.get('/api/status').json
        assert streamed == polled
        assert streamed['percent'] == 75
        assert streamed['errors'] == 1
        assert streamed['revision'] == 1
        assert streamed['agent_queues']['translator_ii'] == 2
    finally:
        response.close()
