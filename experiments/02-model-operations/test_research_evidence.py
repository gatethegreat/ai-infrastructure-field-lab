"""Offline regression checks for the recorded claim boundary; no cloud calls."""
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parent/'evidence'


def evidence(name):
    return json.loads((ROOT/name).read_text(encoding='utf-8'))


class ResearchEvidenceTests(unittest.TestCase):
    def test_allowance_blocks_repetition_without_blocking_other_key(self):
        run=evidence('allowance-20260908T154817Z.json')
        self.assertTrue(run['synthetic_only'])
        self.assertTrue(run['prices_are_synthetic'])
        self.assertEqual(len(run['trials']),3)
        for trial in run['trials']:
            self.assertEqual(len(trial['direct']),11)
            self.assertTrue(all(r['http_status']==200 and r['provider_calls']==1 for r in trial['direct']))
            ordinary=[r for r in trial['gateway'] if r['worker']=='ordinary']
            repetitive=[r for r in trial['gateway'] if r['worker']=='repetitive']
            self.assertEqual([r['http_status'] for r in ordinary],[200]*3)
            self.assertEqual([r['http_status'] for r in repetitive],[200]*4+[429]*4)
            self.assertEqual([r['provider_calls'] for r in repetitive],[1]*4+[0]*4)
            self.assertTrue(all(r.get('error_class')=='budget' for r in repetitive[4:]))

    def test_allowance_accounting_and_overshoot_are_explicit(self):
        run=evidence('allowance-20260908T154817Z.json')
        self.assertTrue(run['counters_reconciled'])
        self.assertEqual(run['containers_remaining'],'')
        self.assertEqual(len(run['accounting']['identities']),6)
        for identity in run['accounting']['identities']:
            expected=.039 if identity['key_alias'].startswith('ordinary') else .052
            self.assertAlmostEqual(identity['max_budget'],.05)
            self.assertAlmostEqual(identity['key_spend'],expected)
            self.assertAlmostEqual(identity['logged_spend'],expected)
        rejected=[r for r in run['accounting']['request_accounting'] if r['status']=='failure']
        self.assertEqual(len(rejected),12)
        self.assertTrue(all(r['spend']==0 for r in rejected))

    def test_real_api_comparison_has_ten_completed_cases(self):
        run=evidence('bedrock-comparison-20260908T145732Z.json')
        self.assertEqual(run['status'],'passed')
        self.assertEqual(run['attempts'],10)
        self.assertEqual(len(run['records']),10)
        self.assertTrue(all(r['status']=='completed' for r in run['records']))

    def test_rejections_do_not_reach_provider(self):
        run=evidence('policy-controls-20260908T151953Z.json')
        checks=run['checks']
        self.assertEqual(checks[0]['provider_requests'],checks[1]['provider_requests'])
        self.assertEqual(checks[1]['http_status'],403)
        rates=[r for r in checks if r['case']=='rate_probe']
        self.assertEqual([r['http_status'] for r in rates],[200,429])
        self.assertEqual(rates[0]['provider_requests'],rates[1]['provider_requests'])

    def test_budget_overshoot_and_restart_discrepancy_stay_visible(self):
        immediate=evidence('policy-controls-20260908T151953Z.json')
        rows={r['key_alias']:r for r in immediate['accounting_after_recovery']['identities']}
        self.assertAlmostEqual(rows['team-a']['key_spend'],.026)
        self.assertAlmostEqual(rows['team-a']['max_budget'],.02)
        self.assertEqual(rows['burst']['key_spend'],0)
        self.assertAlmostEqual(rows['burst']['logged_spend'],.013)
        settled=evidence('policy-controls-20260908T152542Z.json')
        for row in settled['accounting_after_recovery']['identities']:
            self.assertAlmostEqual(row['key_spend'],row['logged_spend'])

    def test_client_exit_zero_is_not_task_success(self):
        run=evidence('codex-task-20260908T152244Z.json')
        self.assertEqual(run['exit_code'],0)
        self.assertFalse(run['successful_file_read'])
        self.assertNotEqual(run['status'],'passed')

    def test_recorded_container_runs_cleaned_up(self):
        for path in list(ROOT.glob('policy-controls-*.json'))+list(ROOT.glob('codex-task-*.json')):
            run=json.loads(path.read_text(encoding='utf-8'))
            self.assertTrue(run['synthetic_only'])
            self.assertEqual(run.get('containers_remaining',run.get('container_remaining')),'')


if __name__=='__main__':unittest.main()
