#!/usr/bin/env python3
"""Purely fictional offline demonstration: no network and no platform writes."""
# © 2026 NovaHelix Corporation & SAKAKIBARA
# SPDX-License-Identifier: GPL-3.0-only
import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import portfolio_sync as sync


def demo():
    root = Path(__file__).resolve().parents[1]
    registry = json.loads((root / 'config/registry.example.json').read_text())
    linear = json.loads((root / 'examples/linear.json').read_text())
    receipt = json.loads((root / 'examples/receipt.json').read_text())
    body = 'Demo acceptance: review a fictional change.'
    receipt['source_body_sha256'] = sync.digest(body)
    source = {'id': 'DEMO_SOURCE', 'url': receipt['source_issue'], 'body': body, 'state': 'OPEN',
              'updatedAt': '2026-01-05T00:00:00Z', 'comments': {'nodes': [{
                  'author': {'login': registry['allowed_owner']}, 'createdAt': receipt['occurred_at'],
                  'url': receipt['source_issue'] + '#issuecomment-1',
                  'body': sync.MARKER + '\n```json\n' + json.dumps(receipt) + '\n```'}]}}
    plan = sync.make_plan({'items': [], 'issues': [source]}, linear, registry)
    partial = copy.deepcopy(receipt)
    partial['scope'] = 'slice'
    try:
        sync.validate_receipt(partial, source, linear[0], registry)
    except sync.Rejected:
        rejected = True
    else:
        rejected = False
    return {'fictional_offline_only': True, 'partial_scope_rejected': rejected, 'plan': plan}


if __name__ == '__main__':
    print(json.dumps(demo(), ensure_ascii=False, indent=2))
