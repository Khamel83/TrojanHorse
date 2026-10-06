"""Deliver a reviewed private batch; verify sources before any native write."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from work_corpus.reminders_bridge import NativeReminders, deliver, initialize


def validate(batch):
    for task in batch['tasks']:
        source = task['source']
        raw = Path(source['source_path']).read_bytes()
        if hashlib.sha256(raw).hexdigest() != source['source_version_id']:
            raise ValueError('source_version_changed')
        document = json.loads(raw)
        text = document['transcript']
        start, end = source['character_range']
        excerpt = text[start:end]
        if excerpt != source['excerpt'] or hashlib.sha256(excerpt.encode()).hexdigest() != source['excerpt_sha256']:
            raise ValueError('source_passage_mismatch')
        if document['id'] != source['source_id']:
            raise ValueError('source_identity_mismatch')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--batch', required=True)
    parser.add_argument('--state', required=True)
    parser.add_argument('--receipt', required=True)
    args = parser.parse_args()
    os.umask(0o077)
    batch = json.loads(Path(args.batch).read_text())
    validate(batch)
    backend = NativeReminders()
    bindings = {}
    for name in ('Trojan-Mine', 'Trojan-Delegated'):
        bindings[name] = backend.call('ensure_list', {'account_id': batch['account_id'], 'name': name})
    con = sqlite3.connect(args.state)
    initialize(con)
    receipts = []
    for task in batch['tasks']:
        task = {**task, 'account_id': batch['account_id'], 'list_id': bindings[task['target_list']]['id']}
        result = deliver(con, backend, task)
        receipts.append(result)
        Path(args.receipt).write_text(json.dumps({'bindings': bindings, 'receipts': receipts}, indent=2))
        print(task['task_id'], result['status'], flush=True)
    snapshots = {name: backend.call('snapshot', {'account_id': batch['account_id'], 'list_id': binding['id']}) for name, binding in bindings.items()}
    Path(args.receipt).write_text(json.dumps({'bindings': bindings, 'receipts': receipts, 'final_snapshots': snapshots}, indent=2))
    if any(r['status'] != 'verified' for r in receipts):
        raise SystemExit('Delivery has unresolved items; reconcile existing reservations before retry.')


if __name__ == '__main__':
    main()
