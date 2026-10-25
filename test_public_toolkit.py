# © 2026 NovaHelix Corporation & SAKAKIBARA
# SPDX-License-Identifier: GPL-3.0-only
import copy
import json
import unittest
from pathlib import Path

import portfolio_sync as s
from scripts.check_publication import violations
from scripts.demo import demo
from test_portfolio_sync import fixture, comment


class PortableConfigurationTests(unittest.TestCase):
    def test_any_team_identifier(self):
        self.assertEqual(s.linear_id('https://linear.app/example/issue/DEV42-19/test'), 'DEV42-19')
        with self.assertRaises(s.Rejected):
            s.linear_id('not-an-identifier')

    def test_shipped_configuration_is_offline_only(self):
        registry = json.loads((Path(__file__).parent / 'config/registry.example.json').read_text())
        with self.assertRaises(s.Rejected):
            s.validate_registry(registry)
        registry['example_only'] = False
        self.assertIs(s.validate_registry(registry), registry)

    def test_custom_statuses_project_and_linear(self):
        registry, source, linear, receipt, snapshot = fixture('review')
        registry['phase_mapping'] = {'review': {'linear': 'Review requested', 'github': 'Review queue'}}
        source['comments']['nodes'] = [comment(receipt)]
        plan = s.make_plan(snapshot, [linear], registry)
        self.assertEqual(plan['operations'][0]['fields']['Status'], 'Review queue')
        self.assertEqual(plan['linear_operations'][0]['state'], 'Review requested')

    def test_custom_terminal_still_requires_prior_completion(self):
        registry, source, linear, receipt, _ = fixture('accepted')
        registry['phase_mapping'] = {'accepted': {'linear': 'Delivered', 'github': 'Accepted'}}
        receipt['acceptance'] = {'all_conditions_met': True, 'scope_body_sha256': s.digest(source['body']), 'owner_receipt_url': source['url']}
        receipt['evidence'][0]['kind'] = 'acceptance'
        source['state'] = 'CLOSED'
        with self.assertRaises(s.Rejected):
            s.validate_receipt(receipt, source, linear, registry)
        linear['status'] = 'Delivered'
        s.validate_receipt(receipt, source, linear, registry)

    def test_ambiguous_completion_mapping_rejected(self):
        for mapping in [{'development': {'linear': 'Done', 'github': 'Building'}},
                        {'review': {'linear': 'In Review', 'github': '完成'}}]:
            with self.subTest(mapping=mapping), self.assertRaises(s.Rejected):
                s.phase_mapping({'phase_mapping': mapping})

    def test_custom_protected_stage_preserved(self):
        registry, _, linear, _, snapshot = fixture()
        registry['phase_mapping'] = {'acceptance_pending': {'linear': 'Client check', 'github': 'Client queue'}}
        snapshot['items'][0]['fieldValues']['nodes'][0]['name'] = 'Client queue'
        linear['status'] = 'In Review'
        self.assertFalse(s.make_plan(snapshot, [linear], registry)['operations'])

    def test_truncated_comment_history_fails_closed(self):
        class Fake(s.GitHub):
            def gql(self, *args):
                return {'repository': {'issue': {'comments': {'pageInfo': {'hasPreviousPage': True}}}}}
        with self.assertRaises(s.Rejected):
            Fake().source('https://github.com/example-org/service-api/issues/1')

    def test_demo_produces_only_tracking_operations(self):
        result = demo()
        self.assertTrue(result['fictional_offline_only'])
        self.assertTrue(result['partial_scope_rejected'])
        self.assertFalse(result['plan']['attention'])
        self.assertEqual(result['plan']['linear_operations'][0]['state'], 'In Review')

    def test_publication_rules_and_private_deny_terms(self):
        self.assertIn('private-deny-term', violations('INTERNAL-ONLY', ['internal-only']))
        self.assertIn('github-token', violations('gh' + 'p_' + 'x' * 36))
        self.assertIn('host-address', violations('10.' + '20.30.40'))
        self.assertFalse(violations('https://github.com/example-org/service-api 192.0.2.1'))

    def test_untrusted_comments_cannot_veto_owner_receipt(self):
        registry, source, linear, receipt, snapshot = fixture('review')
        outsider = comment(receipt)
        outsider['author']['login'] = 'stranger'
        outsider['body'] = s.MARKER + '\nmalformed untrusted content'
        source['comments']['nodes'] = [outsider, comment(receipt)]
        plan = s.make_plan(snapshot, [linear], registry)
        self.assertFalse(plan['attention'])
        self.assertEqual(plan['operations'][0]['fields']['Status'], '待审核')

    def test_emission_ignores_untrusted_nonobject_and_event_copies(self):
        registry, source, linear, receipt, _ = fixture()
        conflicting = dict(receipt, phase='review')
        outsiders = [{'body': s.MARKER + '\n```json\n' + json.dumps(value) + '\n```',
                     'user': {'login': 'stranger'}} for value in [[1], 'string', conflicting]]
        class Fake(s.GitHub):
            posted = None
            def source(self, url):
                return copy.deepcopy(source)
            def api(self, args, payload=None):
                if '?per_page=100' in args[0]:
                    return [outsiders]
                if payload is not None:
                    self.posted = payload['body']
                    return {'id': 1, 'html_url': source['url'] + '#issuecomment-1'}
                return {'body': self.posted}
        adapter = Fake()
        self.assertTrue(adapter.emit(receipt, linear, registry)['created'])
        self.assertIsNotNone(adapter.posted)

    def test_receipt_json_requires_object(self):
        for value in [[1], 'string', True]:
            with self.subTest(value=value), self.assertRaises(s.Rejected):
                s.receipt_from_comment({'body': s.MARKER + '\n```json\n' + json.dumps(value) + '\n```'})


if __name__ == '__main__':
    unittest.main(verbosity=2)
