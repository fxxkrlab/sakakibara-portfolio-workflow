#!/usr/bin/env python3
"""Evidence-based portfolio projection. No source Issue close, merge or deploy API."""
import argparse
import concurrent.futures
import datetime as dt
import fcntl
import hashlib
import json
import re
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

# © 2026 NovaHelix Corporation & SAKAKIBARA
# SPDX-License-Identifier: GPL-3.0-only

PHASES = {
    'backlog': ('Backlog', '待整理'), 'todo': ('Todo', '待开发'),
    'development': ('In Progress', '开发中'), 'review': ('In Review', '待审核'),
    'merge_pending': ('In Review', '待合并'),
    'deployment_pending': ('待部署', '待部署'),
    'acceptance_pending': ('待验收', '待验收'), 'blocked': ('阻塞', '阻塞'),
    'accepted': ('Done', '完成'),
}
VALIDATION = {'待核验', '本地/静态', '服务器CI/数据库', '已部署待验收', '真实用户/客户端验收'}
WRITABLE = {'Status', '验证层级', '下一步', '阻塞原因', 'Branch', 'Linear', '项目'}
MARKER = '<!-- portfolio-progress:v1 -->'
PROTECTED = {'待审核', '待合并', '待部署', '待验收', '完成', '阻塞'}
ORDINARY = {'Backlog': '待整理', 'Todo': '待开发', 'In Progress': '开发中', 'In Review': '待审核'}


class Rejected(ValueError):
    pass


def phase_mapping(registry):
    """Override platform status names without changing evidence phase semantics."""
    overrides = registry.get('phase_mapping', {})
    if set(overrides) - set(PHASES):
        raise Rejected('unknown configured phase')
    result = dict(PHASES)
    for key, value in overrides.items():
        if not isinstance(value, dict) or set(value) != {'linear', 'github'} or any(not isinstance(v, str) or not v.strip() for v in value.values()):
            raise Rejected('phase mapping requires nonempty linear/github names')
        result[key] = (value['linear'], value['github'])
    # Ambiguous state mappings could turn an ordinary event into completion.
    if len({v[1] for v in result.values()}) != len(result):
        raise Rejected('GitHub phase status names must be unique')
    terminal = result['accepted'][0]
    if any(value[0] == terminal for key, value in result.items() if key != 'accepted'):
        raise Rejected('Linear completion status must be exclusive')
    return result


def validate_registry(registry):
    if registry.get('version') != 1 or not registry.get('project_id') or not registry.get('allowed_owner'):
        raise Rejected('registry version/project_id/allowed_owner required')
    rows = registry.get('repositories')
    if not isinstance(rows, list) or not rows:
        raise Rejected('at least one explicitly registered repository required')
    names = []
    for row in rows:
        if not re.fullmatch(r'[\w.-]+/[\w.-]+', row.get('repo', '')) or row.get('mirror_mode') not in {'native', 'linked'} or not row.get('project'):
            raise Rejected('invalid repository registration')
        names.append(row['repo'].lower())
    if len(set(names)) != len(names):
        raise Rejected('duplicate repository registration')
    if registry.get('example_only') is not False:
        raise Rejected('example configuration cannot access connected services')
    phase_mapping(registry)
    return registry


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def digest(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def timestamp(value):
    result = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise Rejected('timestamp requires timezone')
    return result.astimezone(dt.timezone.utc)


def source_url(value):
    match = re.fullmatch(r'https://github\.com/([\w.-]+)/([\w.-]+)/issues/([1-9][0-9]*)', value)
    if not match:
        raise Rejected('exact GitHub Issue URL required')
    return value.lower()


def linear_id(value):
    match = re.search(r'(?:^|/issue/)([A-Z][A-Z0-9]*-[1-9][0-9]*)(?:/|$)', value)
    if not match:
        raise Rejected('exact Linear identifier required')
    return match.group(1)


def unwrap_list(value):
    return value['issues'] if isinstance(value, dict) else value


def bind(issues):
    """Attachments alone establish source identity; a matching title never does."""
    bindings = {}
    for issue in unwrap_list(issues):
        sources = set()
        for attachment in issue.get('attachments', []):
            try:
                sources.add(source_url(attachment.get('url', '')))
            except Rejected:
                continue
        for source in sources:
            bindings.setdefault(source, []).append(issue)
    return bindings


def receipt_from_comment(comment):
    body = comment.get('body', '')
    if MARKER not in body:
        return None
    blocks = re.findall(r'```json\s*\n(.*?)\n```', body, re.S)
    if len(blocks) != 1:
        raise Rejected('receipt must contain exactly one JSON block')
    receipt = json.loads(blocks[0])
    if not isinstance(receipt, dict):
        raise Rejected('receipt JSON must be an object')
    return receipt


def validate_receipt(receipt, source, linear, registry, now=None):
    if receipt.get('schema_version') != 1:
        raise Rejected('unsupported receipt schema')
    uuid.UUID(receipt['event_id'])
    occurred = timestamp(receipt['occurred_at'])
    if occurred > (now or dt.datetime.now(dt.timezone.utc)) + dt.timedelta(minutes=5):
        raise Rejected('future receipt')
    if source_url(receipt['source_issue']) != source_url(source['url']):
        raise Rejected('source mismatch')
    allowed = {r['repo'].lower() for r in registry['repositories']}
    repo = '/'.join(source['url'].split('/')[3:5]).lower()
    if repo not in allowed or repo in {r.lower() for r in registry.get('excluded_repos', [])}:
        raise Rejected('repository not registered')
    if receipt['linear_issue'] != linear['id'] or receipt['linear_uuid'] != linear['uuid']:
        raise Rejected('Linear identity mismatch')
    if receipt['source_body_sha256'] != digest(source['body']):
        raise Rejected('acceptance/source body changed since receipt')
    if receipt['phase'] not in PHASES:
        raise Rejected('unknown phase')
    if receipt.get('scope') != 'issue':
        raise Rejected('partial slice may record facts but cannot advance the whole Issue')
    if not receipt.get('next_step') and receipt['phase'] != 'accepted':
        raise Rejected('next step required')
    if receipt.get('validation', '待核验') not in VALIDATION:
        raise Rejected('unknown verification level')
    evidence = receipt.get('evidence', [])
    if not isinstance(evidence, list) or any(not isinstance(e, dict) or not re.match(r'https://', e.get('url', '')) for e in evidence):
        raise Rejected('inspectable HTTPS evidence required')
    sha = receipt.get('source_sha')
    if sha is not None and not re.fullmatch('[0-9a-f]{40}', sha):
        raise Rejected('full source SHA required')
    if receipt.get('work_kind') == 'code' and receipt['phase'] not in {'backlog', 'todo', 'blocked'} and not sha:
        raise Rejected('code progress requires exact source SHA')
    kinds = {e.get('kind') for e in evidence}
    if receipt['phase'] == 'blocked' and not receipt.get('blocker'):
        raise Rejected('blocker reason required')
    if receipt['phase'] == 'deployment_pending' and not {'review', 'merge'} & kinds:
        raise Rejected('review/merge evidence required for deployment stage')
    if receipt['phase'] == 'acceptance_pending' and not {'deployment', 'delivery'} & kinds:
        raise Rejected('deployment or scoped delivery evidence required; CI is insufficient')
    if receipt.get('validation') == '已部署待验收' and 'deployment' not in kinds:
        raise Rejected('deployment verification requires deployment evidence')
    if receipt.get('validation') == '真实用户/客户端验收' and 'acceptance' not in kinds:
        raise Rejected('client verification requires acceptance evidence')
    # Terminal propagation never initiates completion. Original owners must already
    # have completed BOTH source systems, with a current full-scope receipt.
    if receipt['phase'] == 'accepted':
        approval = receipt.get('acceptance', {})
        if source['state'] != 'CLOSED' or linear['status'] != phase_mapping(registry)['accepted'][0]:
            raise Rejected('original acceptance workflow must already complete both source systems')
        if approval.get('all_conditions_met') is not True or approval.get('scope_body_sha256') != digest(source['body']) or not approval.get('owner_receipt_url') or 'acceptance' not in kinds:
            raise Rejected('current full-scope owner acceptance receipt required')
    if source['state'] == 'CLOSED' and receipt['phase'] != 'accepted':
        raise Rejected('closed source needs owner reconciliation, not automatic reopen')
    return receipt


def choose_receipt(source, linear, registry):
    events = {}
    errors = []
    for comment in source.get('comments', {}).get('nodes', []):
        if MARKER not in comment.get('body', ''):
            continue
        if (comment.get('author') or {}).get('login', '').lower() != registry['allowed_owner'].lower():
            # Public commenters have no receipt authority, including veto power.
            continue
        try:
            receipt = receipt_from_comment(comment)
            key = receipt['event_id']
            if key in events and canonical(events[key][0]) != canonical(receipt):
                raise Rejected('event replay has different payload')
            events[key] = (receipt, comment)
        except (ValueError, KeyError, TypeError) as exc:
            errors.append(str(exc))
    if errors:
        raise Rejected('; '.join(errors))
    if not events:
        return None
    latest, comment = max(events.values(), key=lambda pair: timestamp(pair[0]['occurred_at']))
    if len({r['phase'] for r, _ in events.values() if timestamp(r['occurred_at']) == timestamp(latest['occurred_at'])}) > 1:
        raise Rejected('simultaneous receipts disagree on phase')
    validate_receipt(latest, source, linear, registry)
    # A later unstructured owner update may change deployment scope or blockers.
    # Never silently let an old machine receipt outrank that update.
    later = [c for c in source.get('comments', {}).get('nodes', []) if (c.get('author') or {}).get('login', '').lower() == registry['allowed_owner'].lower() and timestamp(c['createdAt']) > timestamp(comment['createdAt']) and MARKER not in c.get('body', '')]
    if later:
        raise Rejected('newer owner update needs a fresh whole-Issue receipt')
    latest = dict(latest)
    latest['receipt_url'] = comment['url']
    return latest


def field_values(item):
    return {v['field']['name']: v.get('name', v.get('text', '')) for v in item['fieldValues']['nodes'] if v.get('field')}


def make_plan(snapshot, linear, registry):
    phases = phase_mapping(registry)
    protected = {phases[p][1] for p in ('review', 'merge_pending', 'deployment_pending', 'acceptance_pending', 'blocked', 'accepted')}
    ordinary = {phases[p][0]: phases[p][1] for p in ('backlog', 'todo', 'development', 'review')}
    bindings = bind(linear)
    items = {source_url(i['content']['url']): i for i in snapshot['items'] if (i.get('content') or {}).get('__typename') == 'Issue'}
    registered = {r['repo'].lower(): r for r in registry['repositories']}
    plan = {'schema_version': 1, 'project_id': registry['project_id'], 'operations': [], 'linear_operations': [], 'attention': []}
    for source in snapshot['issues']:
        key = source_url(source['url'])
        repo = '/'.join(key.split('/')[3:5])
        if repo not in registered:
            continue
        found = bindings.get(key, [])
        if len(found) != 1:
            plan['attention'].append({'source': source['url'], 'reason': 'missing mirror' if not found else 'duplicate mirrors', 'mirror_mode': registered[repo]['mirror_mode']})
            continue
        issue = found[0]
        item = items.get(key)
        current = field_values(item) if item else {}
        try:
            receipt = choose_receipt(source, issue, registry)
        except (ValueError, KeyError, TypeError) as exc:
            plan['attention'].append({'source': source['url'], 'reason': str(exc)})
            continue
        fields = {'Linear': issue['url']}
        if not current.get('项目'):
            fields['项目'] = registered[repo]['project']
        if receipt:
            linear_state, board_state = phases[receipt['phase']]
            fields['Status'] = board_state
            fields['下一步'] = receipt.get('next_step', '') + '\n回执：' + receipt['receipt_url']
            if 'validation' in receipt:
                fields['验证层级'] = receipt['validation']
            if receipt.get('branch'):
                fields['Branch'] = receipt['branch']
            fields['阻塞原因'] = receipt.get('blocker', '')
            if issue['status'] != linear_state:
                # Source completion stays under the original owner. This never
                # creates Linear Done from a CI, PR or an asserted receipt alone.
                plan['linear_operations'].append({'id': issue['id'], 'uuid': issue['uuid'], 'source': source['url'], 'state': linear_state, 'expected_status': issue['status'], 'expected_updated_at': issue['updatedAt'], 'receipt_url': receipt['receipt_url']})
        else:
            # Native code events can reflect active work, but never regress a
            # known release/acceptance/blocker stage or create terminal states.
            if source['state'] == 'OPEN' and issue['status'] in ordinary and current.get('Status') not in protected:
                fields['Status'] = ordinary[issue['status']]
            elif source['state'] == 'CLOSED' and current.get('Status') != phases['accepted'][1]:
                plan['attention'].append({'source': source['url'], 'reason': 'closed source lacks explicit full acceptance receipt'})
        changes = {k: v for k, v in fields.items() if current.get(k, '') != v}
        if changes:
            plan['operations'].append({'source': source['url'], 'content_id': source['id'], 'item_id': item['id'] if item else None, 'expected_updated_at': source['updatedAt'], 'expected_body_sha256': digest(source['body']), 'linear_guard': {'id': issue['id'], 'uuid': issue['uuid'], 'status': issue['status'], 'updatedAt': issue['updatedAt']}, 'expected_fields': {k: current.get(k, '') for k in changes}, 'fields': changes})
    plan['digest'] = digest(canonical(plan))
    return plan


class GitHub:
    def api(self, args, payload=None):
        executable = shutil.which('gh')
        if executable is None and sys.platform == 'darwin' and Path('/opt/homebrew/bin/gh').is_file():
            executable = '/opt/homebrew/bin/gh'
        if executable is None:
            raise Rejected('GitHub CLI is unavailable; use the existing authenticated installation')
        cmd = [executable, 'api'] + args
        data = None
        if payload is not None:
            cmd += ['--input', '-']
            data = json.dumps(payload)
        result = subprocess.run(cmd, input=data, capture_output=True, text=True, timeout=90)
        if result.returncode:
            raise Rejected('GitHub request failed: ' + result.stderr[:400])
        result = json.loads(result.stdout)
        if isinstance(result, dict) and result.get('errors'):
            raise Rejected('GraphQL request failed')
        return result

    def gql(self, query, variables=None):
        return self.api(['graphql'], {'query': query, 'variables': variables or {}})['data']

    def source(self, url):
        source_url(url)
        owner, repo, _, number = url.split('/')[3:]
        fragment = 'id url body state updatedAt comments(last:100){pageInfo{hasPreviousPage} nodes{id url body createdAt author{login}}}'
        source = self.gql('query($o:String!,$r:String!,$n:Int!){repository(owner:$o,name:$r){issue(number:$n){' + fragment + '}}}', {'o': owner, 'r': repo, 'n': int(number)})['repository']['issue']
        if source is None or source['comments']['pageInfo']['hasPreviousPage']:
            raise Rejected('source unavailable or comment history exceeds supported window; reconcile manually')
        return source

    def project(self, project_id):
        items = []
        cursor = None
        while True:
            q = '''query($p:ID!,$cursor:String){
              node(id:$p){... on ProjectV2{
                fields(first:100){nodes{
                  ... on ProjectV2Field{id name dataType}
                  ... on ProjectV2SingleSelectField{id name options{id name}}
                }}
                items(first:100,after:$cursor){
                  pageInfo{hasNextPage endCursor}
                  nodes{
                    id content{__typename ... on Issue{id url state} ... on PullRequest{id url state isDraft}}
                    fieldValues(first:100){nodes{
                      ... on ProjectV2ItemFieldSingleSelectValue{name field{... on ProjectV2SingleSelectField{id name}}}
                      ... on ProjectV2ItemFieldTextValue{text field{... on ProjectV2Field{id name}}}
                    }}
                  }
                }
              }}
            }'''
            d = self.gql(q, {'p': project_id, 'cursor': cursor})['node']
            items.extend(d['items']['nodes'])
            info = d['items']['pageInfo']
            if not info['hasNextPage']:
                break
            cursor = info['endCursor']
        return {'fields': d['fields']['nodes'], 'items': items}

    def snapshot(self, registry):
        project = self.project(registry['project_id'])
        refs = {i['content']['url'] for i in project['items'] if (i.get('content') or {}).get('__typename') == 'Issue' and '/'.join(i['content']['url'].split('/')[3:5]).lower() in {r['repo'].lower() for r in registry['repositories']}}
        for row in registry['repositories']:
            pages = self.api(['repos/' + row['repo'] + '/issues?state=open&per_page=100', '--paginate', '--slurp'])
            for page in pages:
                refs.update(i['html_url'] for i in page if not i.get('pull_request'))
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            sources = list(pool.map(self.source, sorted(refs)))
        return {**project, 'issues': sources, 'captured_at': dt.datetime.now(dt.timezone.utc).isoformat()}

    def item(self, item_id):
        query = '''query($i:ID!){node(id:$i){... on ProjectV2Item{
          id project{id} content{__typename ... on Issue{id url} ... on PullRequest{id url}}
          fieldValues(first:100){nodes{
            ... on ProjectV2ItemFieldSingleSelectValue{name field{... on ProjectV2SingleSelectField{id name}}}
            ... on ProjectV2ItemFieldTextValue{text field{... on ProjectV2Field{id name}}}
          }}
        }}}'''
        return self.gql(query, {'i': item_id})['node']

    def apply(self, plan, registry, linear):
        unsigned = {k: v for k, v in plan.items() if k != 'digest'}
        if plan['digest'] != digest(canonical(unsigned)) or plan['project_id'] != registry['project_id']:
            raise Rejected('plan identity/digest mismatch')
        result = []
        bindings = bind(linear)
        project = self.project(plan['project_id']) if plan['operations'] else None
        fields = {f['name']: f for f in project['fields'] if 'name' in f} if project else {}
        for operation in plan['operations']:
            repo = '/'.join(source_url(operation['source']).split('/')[3:5])
            if repo not in {r['repo'].lower() for r in registry['repositories']} or repo in {r.lower() for r in registry.get('excluded_repos', [])}:
                raise Rejected('apply source outside registry')
            source = self.source(operation['source'])
            mirrors = bindings.get(source_url(source['url']), [])
            if len(mirrors) != 1 or any(mirrors[0].get(k) != v for k, v in operation['linear_guard'].items()):
                result.append({'source': source['url'], 'status': 'conflict-linear'}); continue
            if source['id'] != operation['content_id'] or source['updatedAt'] != operation['expected_updated_at'] or digest(source['body']) != operation['expected_body_sha256']:
                result.append({'source': source['url'], 'status': 'conflict-source'}); continue
            item = next((i for i in project['items'] if (i.get('content') or {}).get('url', '').lower() == source['url'].lower()), None)
            if item is not None:
                item = self.item(item['id'])
                if item is None or item['project']['id'] != plan['project_id'] or (item.get('content') or {}).get('id') != source['id']:
                    result.append({'source': source['url'], 'status': 'conflict-item'}); continue
            current = field_values(item) if item else {}
            if any(current.get(k, '') != v for k, v in operation['expected_fields'].items()):
                result.append({'source': source['url'], 'status': 'conflict-project'}); continue
            if set(operation['fields']) - WRITABLE:
                raise Rejected('field outside tracking allowlist')
            if operation['fields'].get('Status') == phase_mapping(registry)['accepted'][1]:
                # Revalidate the complete receipt against current source data.
                receipt = choose_receipt(source, mirrors[0], registry)
                if receipt is None or receipt['phase'] != 'accepted':
                    raise Rejected('completion projection gate missing')
            # Preflight all field values before even adding an item.
            for key, value in operation['fields'].items():
                field = fields.get(key)
                if not field or (field.get('options') and not any(o['name'] == value for o in field['options'])):
                    raise Rejected('unknown Project field/option: ' + key)
            if item is None:
                item = self.gql('mutation($p:ID!,$c:ID!){addProjectV2ItemById(input:{projectId:$p,contentId:$c}){item{id}}}', {'p': plan['project_id'], 'c': source['id']})['addProjectV2ItemById']['item']
                item = self.item(item['id'])
                if any(field_values(item).get(k, '') != v for k, v in operation['expected_fields'].items()):
                    result.append({'source': source['url'], 'status': 'conflict-project'}); continue
            for key, value in operation['fields'].items():
                field = fields[key]
                if value == '' and not field.get('options'):
                    self.gql('mutation($p:ID!,$i:ID!,$f:ID!){clearProjectV2ItemFieldValue(input:{projectId:$p,itemId:$i,fieldId:$f}){projectV2Item{id}}}', {'p': plan['project_id'], 'i': item['id'], 'f': field['id']})
                    continue
                data = {'singleSelectOptionId': next(o['id'] for o in field['options'] if o['name'] == value)} if field.get('options') else {'text': value[:3000]}
                self.gql('mutation($p:ID!,$i:ID!,$f:ID!,$v:ProjectV2FieldValue!){updateProjectV2ItemFieldValue(input:{projectId:$p,itemId:$i,fieldId:$f,value:$v}){projectV2Item{id}}}', {'p': plan['project_id'], 'i': item['id'], 'f': field['id'], 'v': data})
            read_item = self.item(item['id'])
            actual = field_values(read_item)
            if any(actual.get(k, '') != v[:3000] for k, v in operation['fields'].items()):
                raise Rejected('Project readback mismatch')
            result.append({'source': source['url'], 'status': 'verified', 'fields': operation['fields']})
        return result

    def emit(self, receipt, linear, registry):
        source = self.source(receipt['source_issue'])
        validate_receipt(receipt, source, linear, registry)
        existing = []
        repo = '/'.join(source['url'].split('/')[3:5])
        number = source['url'].split('/')[-1]
        pages = self.api(['repos/' + repo + '/issues/' + number + '/comments?per_page=100', '--paginate', '--slurp'])
        for comment in [c for page in pages for c in page]:
            if (comment.get('user') or {}).get('login', '').lower() != registry['allowed_owner'].lower():
                continue
            try:
                old = receipt_from_comment(comment)
            except (ValueError, TypeError):
                continue
            if old and old.get('event_id') == receipt['event_id']:
                if canonical(old) != canonical(receipt):
                    raise Rejected('same event ID already has a different payload')
                existing.append(comment['html_url'])
        if existing:
            return {'comment': existing[0], 'created': False}
        body = MARKER + '\n\n进度回执：' + receipt['phase'] + '；下一步：' + receipt.get('next_step', '') + '\n\n```json\n' + json.dumps(receipt, ensure_ascii=False, indent=2) + '\n```'
        result = self.api(['repos/' + repo + '/issues/' + number + '/comments'], {'body': body})
        check = self.api(['repos/' + repo + '/issues/comments/' + str(result['id'])])
        if check['body'] != body:
            raise Rejected('receipt comment readback mismatch')
        return {'comment': result['html_url'], 'created': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--registry', default=str(Path(__file__).parent / 'config/registry.local.json'))
    subs = parser.add_subparsers(dest='command', required=True)
    snap = subs.add_parser('snapshot'); snap.add_argument('--output', required=True)
    plan = subs.add_parser('plan'); plan.add_argument('--snapshot', required=True); plan.add_argument('--linear', required=True); plan.add_argument('--output', required=True)
    apply = subs.add_parser('apply'); apply.add_argument('--plan', required=True); apply.add_argument('--linear', required=True); apply.add_argument('--output', required=True)
    emit = subs.add_parser('emit'); emit.add_argument('--receipt', required=True); emit.add_argument('--linear', required=True)
    args = parser.parse_args()
    load = lambda path: json.loads(Path(path).read_text())
    registry = validate_registry(load(args.registry))
    github = GitHub()
    if args.command == 'snapshot':
        result = github.snapshot(registry)
    elif args.command == 'plan':
        result = make_plan(load(args.snapshot), load(args.linear), registry)
    elif args.command == 'apply':
        runtime = Path(args.registry).resolve().parent.parent / 'runtime'
        runtime.mkdir(exist_ok=True)
        with (runtime / 'sync.lock').open('a') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise Rejected('another local writer holds the coordination lock')
            result = github.apply(load(args.plan), registry, load(args.linear))
    else:
        runtime = Path(args.registry).resolve().parent.parent / 'runtime'
        runtime.mkdir(exist_ok=True)
        with (runtime / 'sync.lock').open('a') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise Rejected('another local writer holds the coordination lock')
            result = github.emit(load(args.receipt), load(args.linear), registry)
    if hasattr(args, 'output'):
        Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps({'output': args.output, 'operations': len(result.get('operations', [])) if isinstance(result, dict) else len(result)}, ensure_ascii=False))
    else:
        print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except (Rejected, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as error:
        print('Rejected: ' + str(error), file=sys.stderr)
        sys.exit(2)
