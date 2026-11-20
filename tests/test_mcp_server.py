"""MCP integration tests: only an ephemeral fake panel is contacted."""
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import unittest
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'mcp' / 'server_panel_mcp.py'


def load_server():
    spec = importlib.util.spec_from_file_location('server_panel_mcp', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakePanel(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def respond(self, body, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))) or b'{}')
        self.server.requests.append(('POST', self.path, body))
        if self.path == '/api/login':
            self.server.logins += 1
            self.respond({'success': True, 'token': 'token-' + str(self.server.logins)})
        else:
            self.respond({'success': True, 'body': body})

    def do_GET(self):
        self.server.requests.append(('GET', self.path, None))
        if self.server.reject_once:
            self.server.reject_once = False
            self.respond({'error': 'Expired'}, 401)
        elif self.headers.get('Authorization') != 'Bearer token-' + str(self.server.logins):
            self.respond({'error': 'Unauthorized'}, 401)
        elif self.path == '/api/redirect':
            self.send_response(302)
            self.send_header('Location', 'http://example.invalid/')
            self.end_headers()
        elif self.path == '/api/status':
            self.respond({'nginx': 'active', 'mysql': 'active'})
        elif self.path == '/api/wordpress/sites':
            self.respond({'success': True, 'sites': []})
        elif self.path.startswith('/api/wordpress/install/'):
            self.server.polls += 1
            self.respond({'status': self.server.job_status if self.server.polls >= 2 else 'running',
                          'logs': list(map(str, range(250))), 'result': {'success': True}})
        elif self.path == '/api/not-json':
            self.send_response(502)
            self.end_headers()
            self.wfile.write(b'<html>Bad gateway</html>')
        else:
            self.respond({'error': 'Not found'}, 404)


class MCPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_server()
        cls.http = ThreadingHTTPServer(('127.0.0.1', 0), FakePanel)
        cls.thread = threading.Thread(target=cls.http.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = 'http://127.0.0.1:' + str(cls.http.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown()
        cls.http.server_close()
        cls.thread.join()

    def setUp(self):
        self.http.logins = self.http.polls = 0
        self.http.reject_once = False
        self.http.job_status = 'done'
        self.http.requests = []
        self.env = {'SERVER_PANEL_URL': self.url, 'SERVER_PANEL_USER': 'tester',
                    'SERVER_PANEL_PASSWORD': 'secret', 'SERVER_PANEL_TOKEN': ''}
        with mock.patch.dict(os.environ, self.env):
            self.server = self.module.MCPServer()

    def rpc(self, method, params=None):
        return self.server.handle({'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params or {}})

    def call(self, tool_name, **arguments):
        return self.rpc('tools/call', {'name': tool_name, 'arguments': arguments})['result']

    def test_initialize_protocols_and_notifications(self):
        for version in ('2024-11-05', '2025-03-26', '2025-06-18', 'unknown'):
            result = self.rpc('initialize', {'protocolVersion': version})['result']
            self.assertEqual(result['protocolVersion'], version if version != 'unknown' else '2025-06-18')
            self.assertEqual(result['capabilities'], {'tools': {}})
            self.assertEqual(result['serverInfo'], {'name': 'cloudycode-server-panel', 'version': '1.0.0'})
            self.assertIn('confirm', result['instructions'].lower())
        self.assertIsNone(self.server.handle({'jsonrpc': '2.0', 'method': 'notifications/initialized'}))
        self.assertIsNone(self.server.handle({'jsonrpc': '2.0', 'method': 'anything'}))
        self.assertEqual(self.rpc('ping')['result'], {})
        self.assertEqual(self.http.requests, [])

    def test_tools_have_schemas_and_safety_annotations(self):
        tools = self.rpc('tools/list')['result']['tools']
        names = {t['name'] for t in tools}
        expected = {'panel_status', 'list_wordpress_sites', 'list_laravel_apps', 'list_codeigniter_apps',
                    'list_php_projects', 'wordpress_core_update_status', 'service_control', 'panel_api',
                    'get_job', 'wait_for_job', 'phpmyadmin_status', 'mysql_query'}
        for prefix in ('wordpress', 'laravel', 'codeigniter', 'php_project'):
            expected.update(prefix + '_' + action for action in ('install', 'delete', 'change_port'))
        self.assertTrue(expected <= names)
        for tool in tools:
            schema = tool['inputSchema']
            self.assertEqual(schema['type'], 'object')
            self.assertIsInstance(schema['required'], list)
            self.assertTrue(set(schema['required']) <= set(schema['properties']))
            for prop in schema['properties'].values():
                self.assertIn('type', prop)
                self.assertIn('description', prop)
            if not tool['annotations'].get('readOnlyHint'):
                self.assertTrue(tool['description'].startswith(('DESTRUCTIVE:', 'CHANGES SERVER:')))
                self.assertIn('Confirm with the user before calling.', tool['description'])
        self.assertFalse(any('auto_login' in n or 'panel_close' in n or n == 'panel_settings' for n in names))

    def test_status_and_list_use_lazy_cached_login(self):
        self.assertEqual(self.http.logins, 0)
        result = self.call('panel_status')
        self.assertFalse(result.get('isError', False))
        self.assertEqual(json.loads(result['content'][0]['text'])['nginx'], 'active')
        self.assertEqual(json.loads(self.call('list_wordpress_sites')['content'][0]['text'])['sites'], [])
        self.assertEqual(self.http.logins, 1)
        self.assertEqual(self.http.requests[0][2], {'username': 'tester', 'password': 'secret'})

    def test_relogin_once_on_401_and_explicit_token(self):
        self.http.reject_once = True
        self.assertFalse(self.call('panel_status').get('isError', False))
        self.assertEqual(self.http.logins, 2)
        self.server.client.token = 'expired'
        self.assertFalse(self.call('panel_status').get('isError', False))
        self.assertEqual(self.http.logins, 3)
        with mock.patch.dict(os.environ, dict(self.env, SERVER_PANEL_TOKEN='token-3')):
            server = self.module.MCPServer()
        result = server.handle({'id': 1, 'method': 'tools/call', 'params': {'name': 'panel_status'}})
        self.assertFalse(result['result'].get('isError', False))
        self.assertEqual(self.http.logins, 3)

    def test_connection_refused_is_tool_error(self):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            url = 'http://127.0.0.1:' + str(sock.getsockname()[1])
            with mock.patch.dict(os.environ, dict(self.env, SERVER_PANEL_URL=url)):
                server = self.module.MCPServer()
            result = server.handle({'id': 1, 'method': 'tools/call', 'params': {'name': 'panel_status'}})['result']
        self.assertTrue(result['isError'])
        self.assertIn('Cannot reach the panel at ' + url, result['content'][0]['text'])

    def test_generic_api_path_guards(self):
        for path in ('/api/panel/close', '/api/panel/open?x=1', '/api/login', '/outside',
                     '//example.com/api/status', '/api/../api/panel/close', '/api/panel/%63lose'):
            self.assertTrue(self.call('panel_api', method='POST', path=path)['isError'], path)
        self.assertEqual(self.http.requests, [])

    def test_validation_before_network(self):
        for name, args in [('service_control', {'service': 'bad', 'action': 'stop'}),
                           ('nginx_logs', {'kind': 'bad'}), ('nginx_get_site_config', {}),
                           ('panel_status', {'extra': True}), ('wait_for_job', {'kind': 'wordpress_install', 'job_id': 'x', 'timeout_seconds': 1801}),
                           ('get_job', {'kind': 'wordpress_install', 'job_id': '../close'})]:
            self.assertTrue(self.call(name, **args)['isError'])
        self.assertEqual(self.http.requests, [])

    def test_wait_for_job_done_and_error_trim_logs(self):
        with mock.patch.object(self.module, 'POLL_INTERVAL', 0):
            for state in ('done', 'error'):
                self.http.polls = 0
                self.http.job_status = state
                result = self.call('wait_for_job', kind='wordpress_install', job_id='job')
                data = json.loads(result['content'][0]['text'])
                self.assertEqual(data['status'], state)
                self.assertEqual(len(data['logs']), 200)
                self.assertEqual(self.http.polls, 2)
                self.assertEqual(result.get('isError', False), state == 'error')

    def test_mysql_sql_maps_to_query(self):
        result = self.call('mysql_query', sql='SELECT 1', database='test')
        self.assertFalse(result.get('isError', False))
        self.assertEqual(self.http.requests[-1], ('POST', '/api/mysql/query', {'query': 'SELECT 1', 'database': 'test'}))

    def test_non_json_http_error_is_clear(self):
        result = self.call('panel_api', method='GET', path='/api/not-json')
        self.assertTrue(result['isError'])
        self.assertIn('502', result['content'][0]['text'])
        self.assertIn('non-JSON', result['content'][0]['text'])

    def test_unknown_method_and_invalid_messages(self):
        self.assertEqual(self.rpc('unknown')['error']['code'], -32601)
        for message in ([], 1, None, {'id': 3}):
            self.assertIn('error', self.server.handle(message))

    def test_stdio_roundtrip_and_parse_error(self):
        messages = ['{bad', json.dumps({'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2024-11-05'}}),
                    json.dumps({'method': 'notifications/initialized'}),
                    json.dumps({'id': 2, 'method': 'tools/call', 'params': {'name': 'panel_status'}})]
        run = subprocess.run([sys.executable, str(SCRIPT)], input='\n'.join(messages) + '\n',
                             capture_output=True, text=True, env=dict(os.environ, **self.env), timeout=10)
        self.assertEqual(run.returncode, 0, run.stderr)
        replies = [json.loads(line) for line in run.stdout.splitlines()]
        self.assertEqual(len(replies), 3)
        self.assertEqual(replies[0]['error']['code'], -32700)
        self.assertEqual(replies[1]['result']['protocolVersion'], '2024-11-05')
        self.assertEqual(json.loads(replies[2]['result']['content'][0]['text'])['mysql'], 'active')


    def test_every_dedicated_route_and_body(self):
        client = self.server.client
        with mock.patch.object(client, 'request', return_value={'success': True}) as request:
            for name, path in self.module.READ_ROUTES.items():
                self.call(name)
                self.assertEqual(request.call_args.args[:2], ('GET', path))
            cases = [
                ('nginx_get_site_config', {'name': 'demo'}, 'GET', '/api/nginx/site/demo', None),
                ('nginx_logs', {'kind': 'access'}, 'GET', '/api/nginx/logs/access', None),
                ('nginx_save_site_config', {'name': 'demo', 'content': 'config'}, 'POST', '/api/nginx/site/demo', {'content': 'config', 'action': 'save'}),
                ('nginx_toggle_site', {'name': 'demo', 'action': 'disable'}, 'POST', '/api/nginx/site/demo', {'action': 'disable'}),
                ('nginx_save_main_config', {'content': 'config'}, 'POST', '/api/nginx/config', {'content': 'config'}),
                ('nginx_validate', {}, 'POST', '/api/nginx/validate', {}),
                ('service_control', {'service': 'nginx', 'action': 'stop'}, 'POST', '/api/services/nginx/stop', {}),
                ('mysql_create_database', {'name': 'demo'}, 'POST', '/api/mysql/databases', {'name': 'demo'}),
                ('mysql_drop_database', {'name': 'demo'}, 'DELETE', '/api/mysql/databases/demo', {}),
                ('wordpress_core_update', {'paths': ['/var/www/demo']}, 'POST', '/api/wordpress/core-update', {'paths': ['/var/www/demo']}),
            ]
            for app, route in self.module.APP_ROUTES.items():
                fields = {'site_name': 'demo', 'db_name': 'db', 'db_user': 'user', 'db_pass': 'pass', 'port': 8301}
                path_key = 'install_path' if app == 'wordpress' else 'path'
                cases.extend([
                    (app + '_install', fields, 'POST', '/api/' + route + '/install', fields),
                    (app + '_delete', {path_key: '/var/www/demo'}, 'DELETE', '/api/' + route + ('/sites' if app == 'wordpress' else '/apps'), {path_key: '/var/www/demo'}),
                    (app + '_change_port', {'nginx_site': 'demo', 'port': 8301}, 'POST', '/api/' + route + '/port', {'nginx_site': 'demo', 'port': 8301}),
                ])
            for name, args, method, path, body in cases:
                with self.subTest(name=name):
                    response = self.call(name, **args)
                    self.assertFalse(response.get('isError', False), response)
                    self.assertEqual(request.call_args.args[:2], (method, path))
                    if body is not None:
                        self.assertEqual(request.call_args.args[2], body)
            for kind, prefix in self.module.JOB_PATHS.items():
                self.call('get_job', kind=kind, job_id='job')
                self.assertEqual(request.call_args.args[:2], ('GET', prefix + 'job'))

    def test_redirects_refused_and_generic_query_preserved(self):
        result = self.call('panel_api', method='GET', path='/api/redirect')
        self.assertTrue(result['isError'])
        self.assertIn('redirect', result['content'][0]['text'].lower())
        with mock.patch.object(self.server.client, 'request', return_value={}) as request:
            self.call('panel_api', method='GET', path='/api/wordpress/credentials?path=%2Fvar%2Fwww%2Fdemo')
            self.assertEqual(request.call_args.args[1], '/api/wordpress/credentials?path=%2Fvar%2Fwww%2Fdemo')

    def test_retry_stops_after_second_401(self):
        with mock.patch.object(self.server.client, '_request', side_effect=urllib.error.HTTPError(self.url, 401, 'Unauthorized', {}, None)):
            with mock.patch.object(self.server.client, 'login') as login:
                self.server.client.token = 'expired'
                self.assertTrue(self.call('panel_status')['isError'])
                self.assertEqual(login.call_count, 1)

    def test_wait_timeout_and_unknown_status(self):
        with mock.patch.object(self.server, 'get_job', return_value={'status': 'running'}):
            with mock.patch.object(self.module.time, 'monotonic', side_effect=[0, 0, 2, 2]):
                with mock.patch.object(self.module.time, 'sleep'):
                    result = self.call('wait_for_job', kind='wordpress_install', job_id='job', timeout_seconds=1)
            self.assertTrue(result['isError'])
            self.assertIn('Timed out', result['content'][0]['text'])
        with mock.patch.object(self.server, 'get_job', return_value={'status': 'unknown'}):
            self.assertTrue(self.call('wait_for_job', kind='wordpress_install', job_id='job')['isError'])

    def test_job_done_with_failed_result_and_text_truncation(self):
        with mock.patch.object(self.server, 'get_job', return_value={'status': 'done', 'result': {'success': False}}):
            self.assertTrue(self.call('wait_for_job', kind='wordpress_core_update', job_id='job')['isError'])
        with mock.patch.object(self.server, 'get_job', return_value={'status': 'done', 'logs': ['first\nsecond'] * 150}):
            data = json.loads(self.call('wait_for_job', kind='wordpress_install', job_id='job')['content'][0]['text'])
            self.assertEqual(len(data['logs']), 200)
            self.assertTrue(all('\n' not in line for line in data['logs']))
        with mock.patch.object(self.server.client, 'request', return_value={'logs': 'x' * 70000}):
            text = self.call('panel_status')['content'][0]['text']
            self.assertIn('Truncated', text)
            self.assertLess(len(text), 60100)

    def test_non_localhost_url_refused_at_startup(self):
        for url in ('http://example.com', 'http://127.0.0.2', 'file:///tmp/panel',
                    'http://localhost@evil.example', 'http://localhost/path', 'http://localhost#fragment'):
            run = subprocess.run([sys.executable, str(SCRIPT)], input='', capture_output=True, text=True,
                                 env=dict(os.environ, **dict(self.env, SERVER_PANEL_URL=url)), timeout=5)
            self.assertEqual(run.returncode, 2, url)
            self.assertEqual(run.stdout, '')
            self.assertIn('localhost', run.stderr.lower())


if __name__ == '__main__':
    unittest.main()
