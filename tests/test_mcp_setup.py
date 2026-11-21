import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
FAKE_CLIENT = """#!/bin/bash
client=${0##*/}
{
  printf '%s' "$client"
  printf '\\t%s' "$@"
  printf '\\n'
} >> "$CLIENT_LOG"
case "$2" in
  get)
    if [[ -f "$HOME/broken-client" ]]; then
      echo 'Client configuration could not be loaded' >&2
      exit 1
    fi
    if [[ -f "$HOME/$client-registered" ]]; then
      echo 'Existing password: fake-legacy-password'
      exit 0
    fi
    if [[ "$client" == claude ]]; then
      echo "No MCP server found with name: $3"
    else
      echo "No MCP server named '$3' found." >&2
    fi
    exit 1
    ;;
  add) : > "$HOME/$client-registered" ;;
  remove) /bin/rm -f "$HOME/$client-registered" ;;
  *) exit 1 ;;
esac
"""


@pytest.fixture
def setup(tmp_path):
    repo = tmp_path / 'example panel'
    scripts = repo / 'scripts'
    scripts.mkdir(parents=True)
    shutil.copy2(ROOT / 'panel.py', repo)
    script = scripts / 'mcp-setup.sh'
    shutil.copy2(ROOT / 'scripts' / script.name, script)
    fake_bin = tmp_path / 'bin'
    fake_bin.mkdir()
    for client in ('claude', 'codex'):
        path = fake_bin / client
        path.write_text(FAKE_CLIENT)
        path.chmod(0o700)
    (fake_bin / 'python3').symlink_to(sys.executable)
    (fake_bin / 'dirname').symlink_to(shutil.which('dirname'))
    home = tmp_path / 'home'
    (home / '.config' / 'opencode').mkdir(parents=True)
    config = tmp_path / 'test-config.json'
    log = tmp_path / 'argv.log'
    env = {'HOME': str(home), 'PATH': str(fake_bin), 'CLIENT_LOG': str(log),
           'SERVER_PANEL_CONFIG': str(config)}

    def run(*args, answer=''):
        proc = subprocess.run(['/bin/bash', str(script), *args], input=answer,
                              cwd=repo, env=env, capture_output=True, text=True, check=True)
        return proc.stdout + proc.stderr
    return run, repo, config, log, home


@pytest.mark.skipif(os.geteuid() == 0, reason='MCP setup intentionally refuses root')
def test_setup_on_status_and_off_preserve_registrations(setup):
    run, repo, config, log, home = setup
    assert 'MCP key: off' in run('status')
    assert not config.exists()
    output = run('on')
    key = json.loads(config.read_text())['mcp_key']
    assert key and key not in output
    assert 'Restart' in output
    snippet = json.JSONDecoder().raw_decode(output[output.index('{'):])[0]
    bridge = str(repo / 'mcp' / 'server_panel_mcp.py')
    assert snippet == {'mcp': {'server-panel': {
        'type': 'local', 'command': ['python3', bridge], 'enabled': True,
    }}}
    assert list((home / '.config' / 'opencode').iterdir()) == []
    entries = log.read_text().splitlines()
    assert '\t'.join(('claude', 'mcp', 'add', 'server-panel', '-s', 'user', '--', 'python3', bridge)) in entries
    assert '\t'.join(('codex', 'mcp', 'add', 'server-panel', '--', 'python3', bridge)) in entries
    output = run('on')
    assert output.count('already registered') == 2
    assert 'fake-legacy-password' not in output
    assert json.loads(config.read_text())['mcp_key'] == key
    assert log.read_text().count('mcp\tadd') == 2
    assert 'MCP key: on' in run('status')
    assert 'password' in run('off', '--yes')
    assert json.loads(config.read_text())['mcp_key'] == ''
    assert 'mcp\tremove' not in log.read_text()
    assert 'MCP key: off' in run('status')
    assert key not in log.read_text()
    assert 'fake-legacy-password' not in log.read_text()


@pytest.mark.skipif(os.geteuid() == 0, reason='MCP setup intentionally refuses root')
def test_setup_explicit_client_removal_and_replacement(setup):
    run, _, _, log, home = setup
    for client in ('claude', 'codex'):
        (home / f'{client}-registered').touch()
    run('on', '--force')
    assert log.read_text().count('mcp\tremove\tserver-panel') == 2
    assert log.read_text().count('mcp\tadd\tserver-panel') == 2
    run('off', answer='\n')
    assert log.read_text().count('mcp\tremove\tserver-panel') == 2
    run('off', '--yes', '--remove-clients')
    assert log.read_text().count('mcp\tremove\tserver-panel') == 4


@pytest.mark.skipif(os.geteuid() == 0, reason='MCP setup intentionally refuses root')
def test_setup_leaves_clients_alone_when_lookup_fails(setup):
    run, _, _, log, home = setup
    (home / 'broken-client').touch()
    assert 'could not check registration' in run('on')
    assert 'could not check registration' in run('status')
    assert 'mcp\tadd' not in log.read_text()
