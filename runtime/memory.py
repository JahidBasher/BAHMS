#!/usr/bin/env python3
"""BAHMS project-local memory CLI, Python stdlib only. Installed at .bahms/memory.py."""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import tempfile
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from core import MemoryStore, estimate_tokens, VALID_KINDS, VALID_RELATIONS

DATA = HERE / 'data'
DB = DATA / 'memory.sqlite'
ACTIVE = DATA / 'active_branch.txt'
EXPORT = HERE / 'export'
SNAPSHOT = HERE / 'shared' / 'memory.json'
DEFAULT_BUDGET = 1400


def store():
    DATA.mkdir(parents=True, exist_ok=True)
    return MemoryStore(DB)


def active_branch():
    if not ACTIVE.is_file():
        raise SystemExit('BAHMS not initialized. Run python3 .bahms/memory.py init')
    return ACTIVE.read_text(encoding='utf-8').strip()


def resolve_branch(option):
    return option or active_branch()


def emit(value):
    print(json.dumps(value, indent=2, ensure_ascii=False, default=str))


def bootstrap(s):
    try:
        s.get_branch('R0')
    except KeyError:
        s.create_branch('R0', ROOT.name, actor='human')
    try:
        s.get_record('PROJECT-001')
    except KeyError:
        s.put_record(record_id='PROJECT-001', kind='project', branch_id='R0',
                     title=f'Project context: {ROOT.name}',
                     summary='Research occurs in this repository. Read existing project documentation for goals, interfaces, and constraints; do not invent them. Persist decisions and evidence through BAHMS.',
                     status='active', pinned=True, source_uri='README.md', actor='human')
    if not ACTIVE.exists():
        ACTIVE.write_text('R0\n', encoding='utf-8')


def make_snapshot(s):
    """Portable snapshot for Git/backups; use explicit checkpoints rather than per-token writes."""
    table_columns = {
        'branches': ['id','name','parent_id','status','checkpoint_id','created_at','updated_at'],
        'records': ['id','kind','branch_id','title','summary','body','status','review_state',
                    'version','pinned','source_uri','created_at','updated_at'],
        'edges': ['source_id','target_id','relation','created_at'],
        'events': ['seq','ts','actor','action','subject_id','payload'],
    }
    with s.connect() as db:
        rows = {}
        for table, cols in table_columns.items():
            rows[table] = [dict(r) for r in db.execute(f'SELECT {", ".join(cols)} FROM {table}')]
    payload = {'format': 'bahms-memory-snapshot-v1', 'tables': rows, 'active_branch': active_branch()}
    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', dir=SNAPSHOT.parent, prefix='.memory-', suffix='.json',
                                     encoding='utf-8', delete=False) as f:
        temp = Path(f.name)
        json.dump(payload, f, indent=2, ensure_ascii=False)
        f.write('\n')
    os.replace(temp, SNAPSHOT)
    return {'snapshot_path': str(SNAPSHOT), 'counts': {k: len(v) for k,v in rows.items()}}


def restore_snapshot(s):
    if not SNAPSHOT.exists():
        raise FileNotFoundError(SNAPSHOT)
    payload = json.loads(SNAPSHOT.read_text(encoding='utf-8'))
    if payload.get('format') != 'bahms-memory-snapshot-v1':
        raise ValueError('Unsupported snapshot format')
    tables = payload['tables']
    with s.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        if db.execute('SELECT COUNT(*) FROM branches').fetchone()[0]:
            db.rollback()
            raise ValueError('Restore refused: database is not empty. Back up or remove it explicitly first.')
        # Parent branches must be inserted before children. Avoid relying on row order.
        branches = {b['id']: b for b in tables['branches']}
        while branches:
            pending = len(branches)
            for bid, branch in list(branches.items()):
                if branch['parent_id'] not in branches:
                    cols = list(branch)
                    db.execute(f'INSERT INTO branches ({", ".join(cols)}) VALUES ({", ".join("?" for _ in cols)})', tuple(branch.values()))
                    del branches[bid]
            if len(branches) == pending:
                raise ValueError('Snapshot contains invalid branch ancestry')
        for table in ['records','edges','events']:
            for record in tables[table]:
                cols = list(record)
                db.execute(f'INSERT INTO {table} ({", ".join(cols)}) VALUES ({", ".join("?" for _ in cols)})', tuple(record.values()))
        db.execute('DELETE FROM records_fts')
        for r in db.execute('SELECT id,title,summary,body FROM records'):
            db.execute('INSERT INTO records_fts (record_id,title,summary,body) VALUES (?,?,?,?)', tuple(r))
        db.commit()
    # Caches intentionally omitted; they are rebuilt on demand.
    ACTIVE.write_text(payload.get('active_branch', 'R0') + '\n', encoding='utf-8')
    return {'restored': True, 'records': len(tables['records']), 'branches': len(tables['branches'])}


def parser():
    p = argparse.ArgumentParser(description='BAHMS: shared, branch-aware, persistent project memory')
    sub = p.add_subparsers(dest='action', required=True)
    sub.add_parser('init', help='Initialize memory; restore portable snapshot if available')
    sub.add_parser('status', help='Show research branches and memory counts')
    sub.add_parser('doctor', help='Check project memory setup and integrity')
    sub.add_parser('snapshot', help='Write a portable JSON snapshot (review before committing to Git)')
    sub.add_parser('restore', help='Restore snapshot into an EMPTY database')
    q=sub.add_parser('branch',help='Create a research branch');q.add_argument('id');q.add_argument('name');q.add_argument('--parent')
    q=sub.add_parser('switch',help='Set the suggested branch for sequential VS Code sessions');q.add_argument('id')
    q=sub.add_parser('context',help='Retrieve bounded task-specific L1 context');q.add_argument('--task',required=True);q.add_argument('--branch');q.add_argument('--budget',type=int,default=DEFAULT_BUDGET)
    q=sub.add_parser('note',help='Store a provisional source-backed note');q.add_argument('--title',required=True);q.add_argument('--summary',required=True);q.add_argument('--source');q.add_argument('--branch')
    q=sub.add_parser('remember',help='Add hypothesis / experiment / claim / decision / finding');q.add_argument('--kind',required=True,choices=sorted(VALID_KINDS));q.add_argument('--title',required=True);q.add_argument('--summary',required=True);q.add_argument('--source');q.add_argument('--branch');q.add_argument('--body-file');q.add_argument('--id')
    q=sub.add_parser('checkpoint',help='Save branch handoff and portable snapshot');q.add_argument('--summary',required=True);q.add_argument('--branch')
    q=sub.add_parser('get',help='Retrieve one full memory record');q.add_argument('id')
    q=sub.add_parser('search',help='Search memory summaries and evidence');q.add_argument('query');q.add_argument('--limit',type=int,default=10)
    q=sub.add_parser('link',help='Connect experiment/claim/hypothesis evidence');q.add_argument('source');q.add_argument('target');q.add_argument('relation',choices=sorted(VALID_RELATIONS))
    sub.add_parser('export',help='Generate read-only, human-readable Markdown views')
    sub.add_parser('cache-stats',help='Show L2/L3 cache stats')
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    s = store()
    if args.action == 'init':
        if SNAPSHOT.exists() and not ACTIVE.exists():
            with s.connect() as db:
                count = db.execute('SELECT COUNT(*) FROM branches').fetchone()[0]
            if not count:
                emit(restore_snapshot(s)); return
        bootstrap(s)
        emit({'initialized':str(DB),'active_branch':active_branch(),'project':str(ROOT)})
        return
    if args.action == 'restore':
        emit(restore_snapshot(s)); return
    if args.action in ('status','doctor'):
        with s.connect() as db:
            branches=[dict(x) for x in db.execute('SELECT id,name,parent_id,checkpoint_id FROM branches ORDER BY id')]
            records=db.execute('SELECT COUNT(*) FROM records').fetchone()[0]
            review=db.execute("SELECT COUNT(*) FROM records WHERE review_state='needs_review'").fetchone()[0]
            integrity=db.execute('PRAGMA integrity_check').fetchone()[0]
        current=active_branch() if ACTIVE.exists() else None
        emit({'project':str(ROOT),'database':str(DB),'active_branch':current,
              'branches':branches,'records':records,'needs_review':review,'sqlite_integrity':integrity,
              'snapshot_exists':SNAPSHOT.exists(), 'ready': bool(current and integrity == 'ok')})
    elif args.action == 'branch':
        parent=args.parent or active_branch()
        emit(s.create_branch(args.id,args.name,parent_id=parent))
    elif args.action == 'switch':
        s.get_branch(args.id)
        ACTIVE.write_text(args.id+'\n',encoding='utf-8')
        emit({'active_branch':args.id, 'note':'Shared default. Use --branch per task if multiple agents run concurrently.'})
    elif args.action == 'context':
        b=resolve_branch(args.branch)
        r=s.get_context(b,args.task,args.budget)
        print(f'BAHMS branch={b} selected={len(r["items"])} estimated_tokens={r["used_est_tokens"]} budget={args.budget}')
        print(r['assembled_text'] or '(No relevant memory. Read source project docs.)')
    elif args.action in ('note','remember'):
        b=resolve_branch(args.branch)
        kind='note' if args.action=='note' else args.kind
        body=Path(args.body_file).read_text(encoding='utf-8') if getattr(args,'body_file',None) else ''
        record_id=(getattr(args,'id',None) or f'{kind.upper()}-{uuid.uuid4().hex[:12]}')
        r=s.put_record(record_id=record_id,kind=kind,title=args.title,summary=args.summary,
                       body=body,branch_id=b,status='draft',source_uri=args.source,actor='agent')
        emit({'saved':r['id'],'kind':kind,'branch':b,'status':'draft'})
    elif args.action=='checkpoint':
        b=resolve_branch(args.branch)
        r=s.checkpoint(b,args.summary)
        outcome=make_snapshot(s)
        emit({'checkpoint':r['id'],'branch':b, **outcome})
    elif args.action=='get':
        emit(s.get_record(args.id))
    elif args.action=='search':
        emit([{'id':x['id'],'title':x['title'],'kind':x['kind'],'branch':x['branch_id'],
               'review_state':x['review_state'],'summary':x['summary'],'source':x['source_uri']} for x in s.search(args.query,args.limit)])
    elif args.action=='link':
        emit(s.link(args.source,args.target,args.relation))
    elif args.action=='export':
        emit({'exported':s.render_markdown(EXPORT),'location':str(EXPORT)})
    elif args.action=='snapshot':
        emit(make_snapshot(s))
    elif args.action=='cache-stats':
        emit(s.cache_stats())

if __name__ == '__main__':
    try:
        main()
    except (sqlite3.Error, KeyError, ValueError, PermissionError, FileNotFoundError) as exc:
        sys.stderr.write(f'BAHMS error: {exc}\n')
        sys.exit(1)
