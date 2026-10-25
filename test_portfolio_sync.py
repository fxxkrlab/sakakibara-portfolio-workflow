# © 2026 NovaHelix Corporation & SAKAKIBARA
# SPDX-License-Identifier: GPL-3.0-only
import copy
import datetime as dt
import json
import unittest
import uuid

import portfolio_sync as s

URL = 'https://github.com/example-org/example/issues/1'
NOW = dt.datetime(2026, 1, 5, 0, 0, tzinfo=dt.timezone.utc)


def fixture(phase='development'):
    registry = {'project_id': 'project', 'allowed_owner': 'example-org', 'repositories': [{'repo': 'example-org/example', 'project': '跨项目', 'mirror_mode': 'linked'}]}
    source = {'id': 'source', 'url': URL, 'body': '原验收条件', 'state': 'OPEN', 'updatedAt': '2026-01-04T23:00:00Z', 'comments': {'nodes': []}}
    linear = {'id': 'ENG-1', 'uuid': str(uuid.uuid4()), 'url': 'https://linear.app/example-org/issue/ENG-1', 'status': 'In Progress', 'updatedAt': '2026-01-04T23:00:00Z', 'attachments': [{'url': URL}]}
    receipt = {'schema_version': 1, 'event_id': str(uuid.uuid4()), 'source_issue': URL, 'linear_issue': linear['id'], 'linear_uuid': linear['uuid'], 'source_body_sha256': s.digest(source['body']), 'phase': phase, 'scope': 'issue', 'work_kind': 'code', 'occurred_at': '2026-01-04T22:00:00Z', 'source_sha': 'a' * 40, 'next_step': '继续按原验收清单验证', 'validation': '本地/静态', 'evidence': [{'kind': 'static', 'url': 'https://github.com/example-org/example/commit/' + 'a' * 40}]}
    item = {'id': 'item', 'content': {'__typename': 'Issue', 'url': URL}, 'fieldValues': {'nodes': [{'field': {'name': 'Status'}, 'name': '开发中'}, {'field': {'name': 'Linear'}, 'text': linear['url']}, {'field': {'name': '项目'}, 'name': '跨项目'}]}}
    snapshot = {'items': [item], 'issues': [source]}
    return registry, source, linear, receipt, snapshot


def comment(receipt, created='2026-01-04T23:00:00Z'):
    return {'body': s.MARKER + '\n```json\n' + json.dumps(receipt) + '\n```', 'url': URL + '#issuecomment-1', 'createdAt': created, 'author': {'login': 'example-org'}}


class ReceiptTests(unittest.TestCase):
    def test_valid_code_receipt(self):
        registry, source, linear, receipt, _ = fixture()
        self.assertEqual(s.validate_receipt(receipt, source, linear, registry, NOW)['phase'], 'development')

    def test_identity_scope_body_and_sha_rejected(self):
        for key, value in [('linear_uuid', str(uuid.uuid4())), ('source_issue', URL.replace('/1', '/2')), ('source_body_sha256', '0' * 64), ('scope', 'slice'), ('source_sha', 'abc'), ('next_step', '')]:
            with self.subTest(key=key):
                registry, source, linear, receipt, _ = fixture(); receipt[key] = value
                with self.assertRaises((s.Rejected, ValueError)):
                    s.validate_receipt(receipt, source, linear, registry, NOW)

    def test_repo_exclusion(self):
        registry, source, linear, receipt, _ = fixture(); registry['excluded_repos'] = ['example-org/example']
        with self.assertRaises(s.Rejected): s.validate_receipt(receipt, source, linear, registry, NOW)

    def test_ci_or_merge_cannot_claim_acceptance_stage(self):
        for kind in ['ci', 'merge']:
            registry, source, linear, receipt, _ = fixture('acceptance_pending'); receipt['evidence'][0]['kind'] = kind
            with self.assertRaises(s.Rejected): s.validate_receipt(receipt, source, linear, registry, NOW)

    def test_delivery_scope_can_await_document_acceptance(self):
        registry, source, linear, receipt, _ = fixture('acceptance_pending'); receipt['evidence'][0]['kind'] = 'delivery'
        self.assertEqual(s.validate_receipt(receipt, source, linear, registry, NOW)['phase'], 'acceptance_pending')

    def test_no_fake_deployed_or_client_validation(self):
        for level in ['已部署待验收', '真实用户/客户端验收']:
            registry, source, linear, receipt, _ = fixture(); receipt['validation'] = level
            with self.assertRaises(s.Rejected): s.validate_receipt(receipt, source, linear, registry, NOW)

    def test_blocker_requires_reason(self):
        registry, source, linear, receipt, _ = fixture('blocked')
        with self.assertRaises(s.Rejected): s.validate_receipt(receipt, source, linear, registry, NOW)

    def test_open_issue_never_completed(self):
        registry, source, linear, receipt, _ = fixture('accepted')
        receipt['acceptance'] = {'all_conditions_met': True, 'scope_body_sha256': s.digest(source['body']), 'owner_receipt_url': URL + '#issuecomment-2'}
        receipt['evidence'][0]['kind'] = 'acceptance'
        with self.assertRaises(s.Rejected): s.validate_receipt(receipt, source, linear, registry, NOW)
        source['state'] = 'CLOSED'
        with self.assertRaises(s.Rejected): s.validate_receipt(receipt, source, linear, registry, NOW)

    def test_completion_requires_already_done_and_full_acceptance(self):
        registry, source, linear, receipt, _ = fixture('accepted'); source['state'] = 'CLOSED'; linear['status'] = 'Done'
        with self.assertRaises(s.Rejected): s.validate_receipt(receipt, source, linear, registry, NOW)
        receipt['acceptance'] = {'all_conditions_met': True, 'scope_body_sha256': s.digest(source['body']), 'owner_receipt_url': URL + '#issuecomment-2'}
        receipt['evidence'][0]['kind'] = 'acceptance'
        self.assertEqual(s.validate_receipt(receipt, source, linear, registry, NOW)['phase'], 'accepted')

    def test_newer_owner_update_invalidates_old_receipt(self):
        registry, source, linear, receipt, _ = fixture(); source['comments']['nodes'] = [comment(receipt), {'body': '发现新的部署问题', 'author': {'login': 'example-org'}, 'createdAt': '2026-01-04T23:30:00Z'}]
        with self.assertRaises(s.Rejected): s.choose_receipt(source, linear, registry)

    def test_replayed_changed_event_rejected(self):
        registry, source, linear, receipt, _ = fixture(); other = dict(receipt, phase='review'); source['comments']['nodes'] = [comment(receipt), comment(other)]
        with self.assertRaises(s.Rejected): s.choose_receipt(source, linear, registry)

    def test_simultaneous_conflicting_events_rejected(self):
        registry, source, linear, receipt, _ = fixture(); other = dict(receipt, event_id=str(uuid.uuid4()), phase='review'); source['comments']['nodes'] = [comment(receipt), comment(other)]
        with self.assertRaises(s.Rejected): s.choose_receipt(source, linear, registry)

    def test_external_receipt_does_not_authorize_projection(self):
        registry, source, linear, receipt, _ = fixture(); c = comment(receipt); c['author']['login'] = 'stranger'; source['comments']['nodes'] = [c]
        self.assertIsNone(s.choose_receipt(source, linear, registry))


class PlanTests(unittest.TestCase):
    def test_native_development_preserves_existing_parent_review(self):
        registry, _, linear, _, snapshot = fixture()
        snapshot['items'][0]['fieldValues']['nodes'][0]['name'] = '待审核'
        self.assertFalse(s.make_plan(snapshot, [linear], registry)['operations'])

    def test_native_ready_review_can_advance_ordinary_development(self):
        registry, _, linear, _, snapshot = fixture(); linear['status'] = 'In Review'
        self.assertEqual(s.make_plan(snapshot, [linear], registry)['operations'][0]['fields']['Status'], '待审核')

    def test_matching_title_without_attachment_is_unlinked(self):
        registry, source, linear, _, snapshot = fixture(); linear['attachments'] = []; linear['title'] = source.get('title', '')
        plan = s.make_plan(snapshot, [linear], registry)
        self.assertFalse(plan['operations']); self.assertEqual(plan['attention'][0]['reason'], 'missing mirror')

    def test_duplicate_mirrors_require_attention(self):
        registry, _, linear, _, snapshot = fixture()
        plan = s.make_plan(snapshot, [linear, copy.deepcopy(linear)], registry)
        self.assertFalse(plan['operations']); self.assertEqual(plan['attention'][0]['reason'], 'duplicate mirrors')

    def test_native_review_does_not_regress_acceptance_or_blocker(self):
        for stage in ['待验收', '待部署', '阻塞', '完成']:
            registry, _, linear, _, snapshot = fixture(); linear['status'] = 'In Review'; snapshot['items'][0]['fieldValues']['nodes'][0]['name'] = stage
            self.assertFalse(s.make_plan(snapshot, [linear], registry)['operations'])

    def test_review_receipt_plans_both_projections(self):
        registry, source, linear, receipt, snapshot = fixture('review'); source['comments']['nodes'] = [comment(receipt)]
        plan = s.make_plan(snapshot, [linear], registry)
        self.assertEqual(plan['operations'][0]['fields']['Status'], '待审核'); self.assertEqual(plan['linear_operations'][0]['state'], 'In Review')
        self.assertNotIn('description', plan['linear_operations'][0])

    def test_repeated_projection_is_noop(self):
        registry, source, linear, receipt, snapshot = fixture(); source['comments']['nodes'] = [comment(receipt)]
        first = s.make_plan(snapshot, [linear], registry)
        fields = s.field_values(snapshot['items'][0]); fields.update(first['operations'][0]['fields'])
        snapshot['items'][0]['fieldValues']['nodes'] = [{'field': {'name': k}, 'text': v} for k, v in fields.items()]
        second = s.make_plan(snapshot, [linear], registry)
        self.assertFalse(second['operations']); self.assertFalse(second['linear_operations'])

    def test_null_project_content_safe(self):
        registry, _, linear, _, snapshot = fixture(); snapshot['items'].append({'id': 'null', 'content': None})
        self.assertFalse(s.make_plan(snapshot, [linear], registry)['operations'])

    def test_closed_without_owner_acceptance_does_not_complete(self):
        registry, source, linear, _, snapshot = fixture(); source['state'] = 'CLOSED'; linear['status'] = 'Done'
        plan = s.make_plan(snapshot, [linear], registry)
        self.assertFalse(plan['operations']); self.assertIn('acceptance', plan['attention'][0]['reason'])

    def test_merged_pr_does_not_complete_parent(self):
        registry, _, linear, _, snapshot = fixture(); snapshot['items'].append({'content': {'__typename': 'PullRequest', 'url': URL.replace('/issues/', '/pull/'), 'state': 'MERGED'}, 'id': 'pr'})
        self.assertFalse(s.make_plan(snapshot, [linear], registry)['operations'])


class ApplyTests(unittest.TestCase):
    def setUp(self):
        self.registry, self.source, self.linear, receipt, self.snapshot = fixture('review')
        self.source['comments']['nodes'] = [comment(receipt)]
        self.plan = s.make_plan(self.snapshot, [self.linear], self.registry)

    def adapter(self):
        test = self
        class Fake(s.GitHub):
            mutations = []
            project_reads = 0
            def source(self, url): return copy.deepcopy(test.source)
            def project(self, project_id):
                self.project_reads += 1
                values = s.field_values(test.snapshot['items'][0])
                fields = [{'id': key, 'name': key} for key in set(values) | s.WRITABLE]
                return {'items': copy.deepcopy(test.snapshot['items']), 'fields': fields}
            def item(self, item_id):
                item = copy.deepcopy(test.snapshot['items'][0])
                item['project'] = {'id': test.registry['project_id']}
                item['content']['id'] = test.source['id']
                return item
            def gql(self, query, variables=None):
                self.mutations.append((query, variables))
                key = variables['f']
                values = s.field_values(test.snapshot['items'][0])
                values[key] = variables.get('v', {}).get('text', '')
                test.snapshot['items'][0]['fieldValues']['nodes'] = [{'field': {'name': k}, 'text': v} for k, v in values.items()]
                return {'updateProjectV2ItemFieldValue': {'projectV2Item': {'id': 'item'}}}
        return Fake()

    def test_source_changed_conflict_performs_no_mutation(self):
        self.source['body'] += ' 新验收条件'
        adapter = self.adapter()
        result = adapter.apply(self.plan, self.registry, [self.linear])
        self.assertEqual(result[0]['status'], 'conflict-source'); self.assertFalse(adapter.mutations)

    def test_linear_changed_conflict_performs_no_mutation(self):
        self.linear['status'] = '阻塞'
        adapter = self.adapter()
        result = adapter.apply(self.plan, self.registry, [self.linear])
        self.assertEqual(result[0]['status'], 'conflict-linear'); self.assertFalse(adapter.mutations)

    def test_project_changed_conflict_performs_no_mutation(self):
        self.snapshot['items'][0]['fieldValues']['nodes'][0]['name'] = '待验收'
        adapter = self.adapter()
        result = adapter.apply(self.plan, self.registry, [self.linear])
        self.assertEqual(result[0]['status'], 'conflict-project'); self.assertFalse(adapter.mutations)

    def test_apply_whitelist_and_readback_preserve_acceptance(self):
        adapter = self.adapter()
        result = adapter.apply(self.plan, self.registry, [self.linear])
        self.assertEqual(result[0]['status'], 'verified')
        self.assertEqual(self.source['body'], '原验收条件'); self.assertEqual(self.source['state'], 'OPEN')
        self.assertTrue(all('ProjectV2ItemFieldValue' in q for q, _ in adapter.mutations))

    def test_tampered_plan_digest_is_rejected(self):
        self.plan['operations'][0]['fields']['Status'] = '完成'
        adapter = self.adapter()
        with self.assertRaises(s.Rejected): adapter.apply(self.plan, self.registry, [self.linear])
        self.assertFalse(adapter.mutations)

    def test_apply_reads_full_board_once_then_individual_item(self):
        adapter = self.adapter()
        result = adapter.apply(self.plan, self.registry, [self.linear])
        self.assertEqual(result[0]['status'], 'verified'); self.assertEqual(adapter.project_reads, 1)

    def test_item_moved_to_another_project_is_not_written(self):
        adapter = self.adapter(); get_item = adapter.item
        adapter.item = lambda ident: dict(get_item(ident), project={'id': 'other-project'})
        result = adapter.apply(self.plan, self.registry, [self.linear])
        self.assertEqual(result[0]['status'], 'conflict-item'); self.assertFalse(adapter.mutations)


if __name__ == '__main__':
    unittest.main(verbosity=2)
