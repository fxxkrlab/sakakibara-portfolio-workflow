#!/usr/bin/env python3
"""Offline publication lint. Matches are reported without disclosing their values."""
# © 2026 NovaHelix Corporation & SAKAKIBARA
# SPDX-License-Identifier: GPL-3.0-only
import argparse
import ipaddress
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RULES = {
    'private-key': r'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----',
    'github-token': r'\bgh[pousr]_[A-Za-z0-9]{30,}\b|\bgithub_pat_[A-Za-z0-9_]{30,}\b',
    'cloud-access-key': r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b',
    'linear-token': r'\blin_api_[A-Za-z0-9]{20,}\b',
    'home-directory': r'/(?:Users|home)/[A-Za-z0-9_.-]+(?:/|\b)',
    'credential-url': r'https?://[^\s/@:]+:[^\s/@]+@',
    'live-project-id': r'\bPVT(?:I|F|SSF)?_[A-Za-z0-9-]{16,}\b',
}


def violations(text, denied=()):
    found = {name for name, pattern in RULES.items() if re.search(pattern, text)}
    for value in re.findall(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', text):
        try:
            address = ipaddress.ip_address(value)
        except ValueError:
            continue
        # Documentation-only addresses and loopback are demonstrable examples.
        if not (address.is_loopback or any(address in ipaddress.ip_network(n) for n in ('192.0.2.0/24', '198.51.100.0/24', '203.0.113.0/24'))):
            found.add('host-address')
    if any(value.casefold() in text.casefold() for value in denied):
        found.add('private-deny-term')
    return sorted(found)


def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args])


def scan(history=False, denied=()):
    failures = []
    paths = set(git('ls-files', '-z', '--cached', '--others', '--exclude-standard').decode().split('\0')) - {''}
    checked = 0
    for name in sorted(paths):
        path = ROOT / name
        if path.is_symlink() or not path.is_file():
            failures.append((name, ['unsupported-path']))
            continue
        try:
            value = name + '\n' + path.read_text(encoding='utf-8')
        except (UnicodeError, OSError):
            failures.append((name, ['non-text-or-unreadable']))
            continue
        checked += 1
        rules = violations(value, denied)
        if rules:
            failures.append((name, rules))
    objects = 0
    if history:
        for row in git('rev-list', '--objects', '--all').decode().splitlines():
            oid, _, name = row.partition(' ')
            kind = git('cat-file', '-t', oid).decode().strip()
            if kind not in {'blob', 'commit', 'tag'}:
                continue
            objects += 1
            try:
                value = name + '\n' + git('cat-file', '-p', oid).decode('utf-8')
            except UnicodeError:
                failures.append(('git-object:' + oid, ['non-text-object']))
                continue
            rules = violations(value, denied)
            if rules:
                failures.append(('git-object:' + oid, rules))
    return checked, objects, failures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--history', action='store_true')
    parser.add_argument('--deny-file', type=Path)
    args = parser.parse_args()
    denied = [] if args.deny_file is None else [s.strip() for s in args.deny_file.read_text().splitlines() if s.strip()]
    checked, objects, failures = scan(args.history, denied)
    for path, rules in failures:
        print(path + ': ' + ', '.join(rules))
    print('Checked %d files and %d reachable objects; violations=%d' % (checked, objects, len(failures)))
    return bool(failures)


if __name__ == '__main__':
    sys.exit(main())
