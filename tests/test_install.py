import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
INSTALL=ROOT/'install_bahms.py'


def run(*args, cwd=None, ok=True):
    p=subprocess.run([sys.executable,*map(str,args)],cwd=cwd,text=True,capture_output=True)
    if ok and p.returncode!=0:
        raise AssertionError(f'{args}: code {p.returncode}\n{p.stdout}\n{p.stderr}')
    return p

class ExistingProjectTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name)
        self.project=self.base/'existing_research_repo'
        self.project.mkdir()
        (self.project/'src').mkdir()
        (self.project/'src'/'model.py').write_text('print("untouched")\n')
        (self.project/'README.md').write_text('# My existing research project\n')
        (self.project/'AGENTS.md').write_text('# Existing Codex rules\nNever remove the training code.\n')
        (self.project/'CLAUDE.md').write_text('# My Claude rules\nFollow established test conventions.\n')
        (self.project/'.gitignore').write_text('__pycache__/\n')
        run(INSTALL,self.project)
        self.cli=self.project/'.bahms'/'memory.py'

    def test_preserves_project_and_instructions(self):
        self.assertEqual((self.project/'src'/'model.py').read_text(),'print("untouched")\n')
        self.assertIn('Never remove the training code.',(self.project/'AGENTS.md').read_text())
        self.assertIn('BAHMS:BEGIN',(self.project/'AGENTS.md').read_text())
        self.assertIn('Follow established test conventions.',(self.project/'CLAUDE.md').read_text())
        self.assertIn('@AGENTS.md',(self.project/'CLAUDE.md').read_text())
        self.assertIn('__pycache__/',(self.project/'.gitignore').read_text())
        self.assertIn('.bahms/data/',(self.project/'.gitignore').read_text())
        self.assertIn('.bahms/shared/',(self.project/'.gitignore').read_text())

    def test_idempotence(self):
        before=(self.project/'AGENTS.md').read_text()
        run(INSTALL,self.project)
        after=(self.project/'AGENTS.md').read_text()
        self.assertEqual(before,after)
        self.assertEqual(after.count('BAHMS:BEGIN'),1)

    def test_branch_write_read_and_cache(self):
        run(self.cli,'branch','H1','New research idea','--parent','R0',cwd=self.project)
        run(self.cli,'switch','H1',cwd=self.project)
        run(self.cli,'remember','--kind','experiment','--title','Token budget trial',
            '--summary','Validated lower latency on sample benchmark','--source','reports/trial.md',cwd=self.project)
        response=run(self.cli,'context','--task','token budget trial','--budget','1400',cwd=self.project)
        self.assertIn('Token budget trial',response.stdout)
        run(self.cli,'checkpoint','--summary','Evaluated budget trial, next rerun on larger corpus',cwd=self.project)
        status=json.loads(run(self.cli,'status',cwd=self.project).stdout)
        self.assertEqual(status['active_branch'],'H1')
        self.assertEqual(status['sqlite_integrity'],'ok')
        self.assertTrue(status['snapshot_exists'])
        self.assertGreater(status['records'],2)
        stats=json.loads(run(self.cli,'cache-stats',cwd=self.project).stdout)
        self.assertTrue(stats)

    def test_snapshot_portability(self):
        run(self.cli,'branch','H2','Alternative','--parent','R0',cwd=self.project)
        run(self.cli,'checkpoint','--branch','H2','--summary','Paused for other tests',cwd=self.project)
        clone=self.base/'another_machine_repo'
        clone.mkdir()
        run(INSTALL,clone)
        shutil_snap=self.project/'.bahms'/'shared'/'memory.json'
        clone_snap=clone/'.bahms'/'shared'/'memory.json'
        clone_snap.parent.mkdir(parents=True,exist_ok=True)
        clone_snap.write_bytes(shutil_snap.read_bytes())
        # Clear ONLY local data in fake clone, retain snapshot.
        for f in (clone/'.bahms'/'data').glob('*'):
            f.unlink()
        run(clone/'.bahms'/'memory.py','init',cwd=clone)
        res=json.loads(run(clone/'.bahms'/'memory.py','status',cwd=clone).stdout)
        self.assertIn('H2',[b['id'] for b in res['branches']])
        self.assertEqual(res['active_branch'],'R0')

    def test_cross_agent_same_database(self):
        # Different agents simply invoke the same shared backend.
        first=run(self.cli,'note','--title','Finding by Claude',
                  '--summary','Experiment hypothesis pending verification',cwd=self.project)
        second=run(self.cli,'search','Finding by Claude',cwd=self.project)
        self.assertIn('Finding by Claude',second.stdout)

if __name__=='__main__': unittest.main()
