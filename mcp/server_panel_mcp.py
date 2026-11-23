#!/usr/bin/env python3
"""Standard-library MCP stdio bridge to the localhost server panel (Python 3.8+)."""
import errno
import json
import math
import os
from pathlib import Path
import posixpath
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

POLL_INTERVAL = 2
MAX_TEXT = 60000
PROTOCOLS = ('2024-11-05', '2025-03-26', '2025-06-18')
JOB_PATHS = {
    '{}_{}'.format(kind, action): '/api/{}/{}/'.format(route, action)
    for kind, route in (('wordpress', 'wordpress'), ('laravel', 'laravel'),
                        ('codeigniter', 'codeigniter'), ('php_project', 'php-projects'))
    for action in ('install', 'delete')
}
JOB_PATHS['wordpress_core_update'] = '/api/wordpress/core-update/'
BLOCKED_PATHS = {
    '/api/login',
    '/api/panel/open',
    '/api/panel/close',
    '/api/secrets/reveal',
    '/api/wordpress/credentials',
    '/api/wordpress/change_db_password',
    '/api/wordpress/change_wp_admin',
}


def normalize_blocked_path(path):
    if not isinstance(path, str):
        return ""
    clean = urllib.parse.urlsplit(path).path
    for _ in range(3):
        decoded = urllib.parse.unquote(clean)
        if decoded == clean:
            break
        clean = decoded
    clean = re.sub(r'/+', '/', clean)
    clean = posixpath.normpath(clean)
    if len(clean) > 1 and clean.endswith('/'):
        clean = clean.rstrip('/')
    return clean.lower()


BLOCKED_NORMALIZED = {normalize_blocked_path(p) for p in BLOCKED_PATHS}


def is_blocked_path(path):
    return normalize_blocked_path(path) in BLOCKED_NORMALIZED


class ToolError(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ToolError('Panel redirects are refused; configure its direct localhost URL.')


class PanelClient:
    def __init__(self):
        self.url = os.environ.get('SERVER_PANEL_URL', 'http://127.0.0.1:8765').rstrip('/')
        try:
            parsed = urllib.parse.urlsplit(self.url)
            valid = (parsed.scheme in ('http', 'https')
                     and parsed.hostname in ('127.0.0.1', 'localhost', '::1')
                     and parsed.username is None and parsed.password is None
                     and not parsed.path and not parsed.query and not parsed.fragment
                     and not any(c.isspace() for c in self.url))
            parsed.port  # Reject malformed ports before any request.
        except ValueError:
            valid = False
        if not valid:
            raise ValueError('SERVER_PANEL_URL must be a localhost HTTP(S) origin (127.0.0.1, localhost, or ::1).')
        self.username = os.environ.get('SERVER_PANEL_USER', 'admin')
        self.password = os.environ.get('SERVER_PANEL_PASSWORD')
        self.config = Path(os.environ.get('SERVER_PANEL_CONFIG') or
                           Path(__file__).resolve().parents[1] / 'panel_config.json')
        self.using_mcp_key = False
        self.token = os.environ.get('SERVER_PANEL_TOKEN') or None
        # Do not send credentials through environment proxies or follow redirects.
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def _request(self, method, path, body, timeout, authenticated=True):
        headers = {'Accept': 'application/json'}
        if authenticated:
            headers['Authorization'] = 'Bearer ' + self.token
        payload = None
        if body is not None:
            payload = json.dumps(body, allow_nan=False).encode('utf-8')
            headers['Content-Type'] = 'application/json'
        req = urllib.request.Request(self.url + path, data=payload, headers=headers, method=method)
        try:
            response = self.opener.open(req, timeout=timeout)
        except urllib.error.HTTPError as exc:
            if exc.code == 401:
                exc.close()
                raise
            response = exc
        except (urllib.error.URLError, OSError) as exc:
            reason = getattr(exc, 'reason', exc)
            if isinstance(reason, ConnectionRefusedError) or getattr(reason, 'errno', None) == errno.ECONNREFUSED:
                raise ToolError('Cannot reach the panel at {}. Start it with python3 panel.py.'.format(self.url)) from None
            raise ToolError('Cannot reach the panel at {}: {}.'.format(self.url, reason)) from None
        with response:
            status = response.code
            raw = response.read()
        try:
            data = json.loads(raw)
        except (ValueError, UnicodeError):
            raise ToolError('Panel returned a non-JSON response (HTTP {}).'.format(status)) from None
        if status >= 400:
            raise ToolError('Panel request failed (HTTP {}): {}'.format(status, json.dumps(data)))
        return data

    def login(self, timeout):
        try:
            data = self._request('POST', '/api/login', {'username': self.username, 'password': self.password},
                                 timeout, authenticated=False)
        except urllib.error.HTTPError:
            raise ToolError('Panel login failed (HTTP 401). Check SERVER_PANEL_USER and SERVER_PANEL_PASSWORD.') from None
        if not isinstance(data, dict) or not data.get('success') or not isinstance(data.get('token'), str) or not data['token']:
            raise ToolError('Panel login failed: no authentication token was returned.')
        self.token = data['token']

    def load_mcp_key(self):
        try:
            with self.config.open() as file:
                config = json.load(file)
        except FileNotFoundError:
            config = {}
        except (OSError, ValueError):
            raise ToolError('Could not read panel config. Check SERVER_PANEL_CONFIG.') from None
        key = config.get('mcp_key') if isinstance(config, dict) else None
        if not isinstance(key, str) or not key:
            raise ToolError('MCP is off. Run scripts/mcp-setup.sh on.')
        self.token = key
        self.using_mcp_key = True

    def request(self, method, path, body=None, timeout=30):
        if is_blocked_path(path):
            raise ToolError('This route is forbidden for agents: {}.'.format(path))
        if not self.token:
            if self.password is not None:
                self.login(timeout)
            else:
                self.load_mcp_key()
        for attempt in range(2):
            try:
                return self._request(method, path, body, timeout)
            except urllib.error.HTTPError:
                if self.using_mcp_key:
                    raise ToolError('MCP key rejected — MCP may have been turned off (scripts/mcp-setup.sh on).') from None
                if self.password is None:
                    raise ToolError('Panel rejected SERVER_PANEL_TOKEN (HTTP 401).') from None
                if attempt:
                    raise ToolError('Panel rejected authentication after re-login (HTTP 401).') from None
                self.token = None
                self.login(timeout)


def field(description, type='string', **kwargs):
    return dict(type=type, description=description, **kwargs)


def tool(name, description, properties=None, required=(), read=False, destructive=False):
    if not read:
        description = ('DESTRUCTIVE: ' if destructive else 'CHANGES SERVER: ') + description + ' Confirm with the user before calling.'
    return {'name': name, 'description': description,
            'inputSchema': {'type': 'object', 'properties': properties or {}, 'required': list(required),
                            'additionalProperties': False},
            'annotations': {'readOnlyHint': read, 'destructiveHint': destructive}}


READ_ROUTES = {
    'panel_status': '/api/status',
    'list_wordpress_sites': '/api/wordpress/sites',
    'list_laravel_apps': '/api/laravel/apps',
    'list_codeigniter_apps': '/api/codeigniter/apps',
    'list_php_projects': '/api/php-projects/apps',
    'list_projects': '/api/projects',
    'wordpress_core_update_status': '/api/wordpress/core-update-status',
    'nginx_list_sites': '/api/nginx/sites',
    'nginx_get_main_config': '/api/nginx/config',
    'mysql_list_databases': '/api/mysql/databases',
    'performance_get_settings': '/api/performance',
    'phpmyadmin_status': '/api/phpmyadmin/status',
}
PORT = field('TCP port to serve this site.', 'integer', minimum=1, maximum=65535)
NAME = field('Nginx site configuration filename.', pattern=r'^[\w.-]+$')
JOB_FIELDS = {'kind': field('Job operation whose polling route to use.', enum=list(JOB_PATHS)),
              'job_id': field('Job ID returned by the initiating operation.', pattern=r'^[A-Za-z0-9_-]+$')}
READ_DESCRIPTIONS = {
    'panel_status': 'Get Nginx/MySQL service state plus CPU, memory, disk, uptime and hostname.',
    'list_wordpress_sites': 'List local WordPress installs with path, database, DB user, Nginx site, port and version.',
    'list_laravel_apps': 'List local Laravel apps with path, database, Nginx site and port.',
    'list_codeigniter_apps': 'List local CodeIgniter 4 apps with path, database, Nginx site and port.',
    'list_php_projects': 'List panel-created plain PHP projects with path, optional database, Nginx site and port.',
    'list_projects': 'List registered projects with their parts, URLs, folders and local running status.',
    'get_project': 'Get a single registered project by its ID or case-insensitive name.',
    'wordpress_core_update_status': 'Get the latest cached WordPress version and the shared core-update cache state.',
    'nginx_list_sites': 'List Nginx virtual hosts and whether each one is enabled.',
    'nginx_get_main_config': 'Read the main nginx.conf file.',
    'mysql_list_databases': 'List MySQL/MariaDB databases.',
    'performance_get_settings': 'Read the tuned Nginx, PHP, PHP-FPM and MySQL performance settings.',
    'phpmyadmin_status': 'Get phpMyAdmin install state, its Nginx site and PHP-FPM status.',
}
TOOLS = [tool(name, READ_DESCRIPTIONS[name], read=True) for name in READ_ROUTES]
TOOLS += [
    tool('get_project', READ_DESCRIPTIONS['get_project'],
         {'id': field('Project ID (8 lowercase hex characters).'),
          'name': field('Case-insensitive project name.')},
         read=True),
    tool('nginx_get_site_config', 'Read a site configuration.', {'name': NAME}, ('name',), read=True),
    tool('nginx_logs', 'Read the last 200 lines of a Nginx log.',
         {'kind': field('Log kind.', enum=['error', 'access'])}, ('kind',), read=True),
    tool('get_job', 'Read a background job, including its status, logs, and result.', JOB_FIELDS,
         ('kind', 'job_id'), read=True),
    tool('service_control', 'Start, stop, restart, or reload a service.',
         {'service': field('Panel-supported service.', enum=['nginx', 'mysql', 'mariadb', 'php8.3-fpm', 'php8.2-fpm', 'php8.1-fpm', 'php8.0-fpm', 'php7.4-fpm']),
          'action': field('Service action.', enum=['start', 'stop', 'restart', 'reload'])},
         ('service', 'action'), destructive=True),
    tool('nginx_save_site_config', 'Overwrite a site configuration.',
         {'name': NAME, 'content': field('Complete Nginx site configuration.')}, ('name', 'content'), destructive=True),
    tool('nginx_save_main_config', 'Overwrite the main Nginx configuration after validation.',
         {'content': field('Complete nginx.conf content.')}, ('content',), destructive=True),
    tool('nginx_toggle_site', 'Enable or disable a Nginx site.',
         {'name': NAME, 'action': field('Site action.', enum=['enable', 'disable'])}, ('name', 'action'), destructive=True),
    tool('nginx_validate', 'Test the Nginx configuration with nginx -t. Changes nothing.', read=True),
    tool('mysql_create_database', 'Create a database.', {'name': field('Database name.', pattern=r'^[\w-]+$')}, ('name',)),
    tool('mysql_drop_database', 'Permanently drop a database.', {'name': field('Database name.', pattern=r'^[\w-]+$')}, ('name',), destructive=True),
    tool('mysql_query', 'Execute arbitrary SQL, which can modify or delete data.',
         {'sql': field('SQL sent as the API query field.'), 'database': field('Optional database; API defaults to _none_.')},
         ('sql',), destructive=True),
    tool('wordpress_core_update', 'Update WordPress core at the selected install paths; returns a job ID.',
         {'paths': field('WordPress installation paths.', 'array', items={'type': 'string'}, minItems=1)}, ('paths',), destructive=True),
    tool('wait_for_job', 'Wait for a background job (install, delete, core update) to finish and return its final status and log tail. Only reads; starts nothing.',
         dict(JOB_FIELDS, timeout_seconds=field('Maximum wait in seconds.', 'number', default=600, minimum=1, maximum=1800)),
         ('kind', 'job_id'), read=True),
    tool('panel_api', 'Call any other panel API route. Login and panel open/close routes are forbidden.',
         {'method': field('HTTP method.', enum=['GET', 'POST', 'DELETE']),
          'path': field('Absolute /api/ path, optionally with query parameters; no URL origin.'),
          'body': field('Optional JSON request object.', 'object')}, ('method', 'path'), destructive=True),
]
APP_ROUTES = {'wordpress': 'wordpress', 'laravel': 'laravel', 'codeigniter': 'codeigniter', 'php_project': 'php-projects'}
for app, route in APP_ROUTES.items():
    install = {
        'site_name': field('Site directory and configuration name; panel provides a default except for WordPress.'),
        'install_path': field('Absolute installation directory under an allowed panel web root; defaults to /var/www/<site_name>.'),
        'db_name': field('Database name; generated by panel if omitted except for WordPress.'),
        'db_user': field('Database user; generated by panel if omitted except for WordPress.'),
        'db_pass': field('Database password; generated by panel if omitted except for WordPress.'),
        'port': dict(PORT, description='TCP port; defaults: WordPress 8090, Laravel 8100, CodeIgniter 8200, PHP 8300. WordPress requires this field.'),
    }
    if app == 'wordpress':
        install.update(wp_title=field('Site title.'), wp_admin=field('WordPress admin username; generated if omitted.'),
                       wp_admin_pass=field('WordPress admin password; generated if omitted.'),
                       wp_email=field('Admin email; default admin@localhost.local.'),
                       selected_plugins=field('Selected panel plugin-library IDs.', 'array', items={'type': 'string'}))
    elif app == 'laravel':
        install.update(app_name=field('Application display name; defaults to site name.'),
                       laravel_version=field('Laravel version; default latest.', enum=['latest', '12']))
    elif app == 'php_project':
        install['template'] = field('Project template; php_db creates a database. Default php.', enum=['blank', 'php', 'php_db'])
    path_key = 'install_path' if app == 'wordpress' else 'path'
    delete = {path_key: field('Absolute installation path to permanently delete.'),
              'db_name': field('Database to drop, if present.'), 'db_user': field('Database user to remove, if present.'),
              'nginx_site': field('Nginx site configuration to remove, if present.')}
    TOOLS.extend([
        tool(app + '_install', 'Install a {} site; returns a job ID.'.format(app), install,
             ('site_name', 'db_name', 'db_user', 'db_pass', 'port') if app == 'wordpress' else ()),
        tool(app + '_delete', 'Delete {} files and specified database, user, and Nginx configuration; returns a job ID.'.format(app),
             delete, (path_key,), destructive=True),
        tool(app + '_change_port', 'Change the {} Nginx port.'.format(app),
             {'nginx_site': field('Existing Nginx site configuration filename.'), 'port': PORT},
             ('nginx_site', 'port'), destructive=True),
    ])
TOOLS_BY_NAME = {t['name']: t for t in TOOLS}


def validate(value, schema, label='arguments'):
    kind = schema['type']
    valid = {'object': isinstance(value, dict), 'string': isinstance(value, str),
             'integer': isinstance(value, int) and not isinstance(value, bool),
             'number': isinstance(value, (int, float)) and not isinstance(value, bool),
             'array': isinstance(value, list)}.get(kind, False)
    if not valid:
        raise ToolError('{} must be {}.'.format(label, kind))
    if 'enum' in schema and value not in schema['enum']:
        raise ToolError('{} must be one of {}.'.format(label, ', '.join(map(str, schema['enum']))))
    if kind == 'object':
        for key in schema.get('required', []):
            if key not in value:
                raise ToolError('Missing required argument: {}.'.format(key))
        for key, item in value.items():
            if key in schema.get('properties', {}):
                validate(item, schema['properties'][key], key)
            elif schema.get('additionalProperties') is False:
                raise ToolError('Unknown argument: {}.'.format(key))
    if kind == 'string' and 'pattern' in schema and not re.fullmatch(schema['pattern'], value):
        raise ToolError('{} has an invalid format.'.format(label))
    if kind in ('integer', 'number'):
        if not math.isfinite(value) or value < schema.get('minimum', -math.inf) or value > schema.get('maximum', math.inf):
            raise ToolError('{} is outside the allowed range.'.format(label))
    if kind == 'array':
        if len(value) < schema.get('minItems', 0):
            raise ToolError('{} must not be empty.'.format(label))
        for item in value:
            validate(item, schema['items'], label + ' item')


def safe_api_path(path):
    if is_blocked_path(path):
        raise ToolError('This route is forbidden for agents: {}.'.format(path))
    parsed = urllib.parse.urlsplit(path)
    decoded = urllib.parse.unquote(parsed.path)
    if (not path.startswith('/api/') or parsed.scheme or parsed.netloc or parsed.fragment
            or any(c.isspace() or ord(c) < 32 for c in path)
            or '\\' in path or decoded != parsed.path
            or any(part in ('.', '..', '') for part in parsed.path.split('/')[1:])):
        raise ToolError('Path must be a direct /api/ route without traversal, encoded path segments, or a URL origin.')
    return path


REDACT_KEY_RE = re.compile(
    r'(?i)(database\.default\.password|db_password|wp_admin_pass|db_pass|api[_-]key|mcp_key|password|passwd|secret|token|pass)'
)
REDACT_LINE_RE = re.compile(
    r'(?im)\b(?P<label>database\.default\.password|db[ _]password|wp_admin_pass|db[ _]pass|api[_-]key|mcp_key|password|passwd|secret|token|pass)\b\s*[:=]\s*\S+.*$'
)


def redact_secrets(data):
    if isinstance(data, dict):
        out = {}
        for k, v in data.items():
            if (isinstance(k, str)
                    and not k.lower().startswith('has_')
                    and isinstance(v, str)
                    and REDACT_KEY_RE.search(k)):
                out[k] = '[redacted]'
            else:
                out[k] = redact_secrets(v)
        return out
    if isinstance(data, list):
        return [redact_secrets(item) for item in data]
    if isinstance(data, str):
        return REDACT_LINE_RE.sub(r'\g<label>: [redacted]', data)
    return data


def result(data, error=False):
    text = data if isinstance(data, str) else json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False)
    if len(text) > MAX_TEXT:
        text = text[:MAX_TEXT] + '\n[Truncated: response exceeded 60,000 characters.]'
    return {'content': [{'type': 'text', 'text': text}], 'isError': error}


class MCPServer:
    def __init__(self):
        self.client = PanelClient()

    def get_job(self, args, timeout=120):
        return self.client.request('GET', JOB_PATHS[args['kind']] + args['job_id'], timeout=timeout)

    def execute(self, name, args):
        if name in READ_ROUTES:
            return self.client.request('GET', READ_ROUTES[name])
        if name == 'get_job':
            return self.get_job(args)
        if name == 'wait_for_job':
            deadline = time.monotonic() + args.get('timeout_seconds', 600)
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ToolError('Timed out waiting for job {}. Use get_job to check it; the job may still be running.'.format(args['job_id']))
                job = self.get_job(args, timeout=min(120, remaining))
                if not isinstance(job, dict):
                    raise ToolError('Panel returned an invalid job response.')
                if job.get('status') in ('done', 'error'):
                    job = dict(job)
                    if isinstance(job.get('logs'), list):
                        lines = []
                        for entry in job['logs'][-200:]:
                            lines.extend(str(entry).splitlines() or [''])
                        job['logs'] = lines[-200:]
                    elif isinstance(job.get('logs'), str):
                        job['logs'] = '\n'.join(job['logs'].splitlines()[-200:])
                    return job
                if job.get('status') != 'running':
                    raise ToolError('Panel returned an unknown job status: {}.'.format(job.get('status')))
                time.sleep(min(POLL_INTERVAL, max(0, deadline - time.monotonic())))
        if name == 'get_project':
            project_id = args.get('id')
            project_name = args.get('name')
            if not project_id and not project_name:
                raise ToolError('Either id or name must be provided to get_project.')
            data = self.client.request('GET', '/api/projects')
            projects = data.get('projects', []) if isinstance(data, dict) else []
            target_id = (project_id or '').strip().lower()
            target_name = (project_name or '').strip().lower()
            for p in projects:
                if target_id and p.get('id', '').lower() == target_id:
                    return p
                if target_name and p.get('name', '').strip().lower() == target_name:
                    return p
            lookup = project_id if project_id else project_name
            raise ToolError('Project not found: {}'.format(lookup))
        if name == 'panel_api':
            path = safe_api_path(args['path'])
            return self.client.request(args['method'], path, args.get('body'), timeout=120)
        if name == 'nginx_logs':
            return self.client.request('GET', '/api/nginx/logs/' + args['kind'])
        if name == 'nginx_get_site_config':
            return self.client.request('GET', '/api/nginx/site/' + urllib.parse.quote(args['name'], safe=''))
        body = dict(args)
        method = 'POST'
        if name == 'service_control':
            path = '/api/services/{service}/{action}'.format(**args)
            body = {}
        elif name in ('nginx_save_site_config', 'nginx_toggle_site'):
            path = '/api/nginx/site/' + urllib.parse.quote(body.pop('name'), safe='')
            if name == 'nginx_save_site_config':
                body['action'] = 'save'
        elif name == 'nginx_save_main_config':
            path = '/api/nginx/config'
        elif name == 'nginx_validate':
            path = '/api/nginx/validate'
        elif name == 'mysql_create_database':
            path = '/api/mysql/databases'
        elif name == 'mysql_drop_database':
            path = '/api/mysql/databases/' + urllib.parse.quote(body.pop('name'), safe='')
            method = 'DELETE'
        elif name == 'mysql_query':
            path = '/api/mysql/query'
            body['query'] = body.pop('sql')
        elif name == 'wordpress_core_update':
            path = '/api/wordpress/core-update'
        else:
            app, action = next((app, name[len(app) + 1:]) for app in APP_ROUTES if name.startswith(app + '_'))
            route = APP_ROUTES[app]
            if action == 'install':
                path = '/api/' + route + '/install'
            elif action == 'delete':
                path = '/api/' + route + ('/sites' if app == 'wordpress' else '/apps')
                method = 'DELETE'
            else:
                path = '/api/' + route + '/port'
        return self.client.request(method, path, body, timeout=120 if name.endswith(('_install', '_delete', '_core_update')) else 30)

    def call_tool(self, params):
        try:
            if not isinstance(params, dict):
                raise ToolError('Tool call params must be an object.')
            name = params.get('name')
            if not isinstance(name, str) or name not in TOOLS_BY_NAME:
                raise ToolError('Unknown tool: {}.'.format(name))
            args = params.get('arguments', {})
            validate(args, TOOLS_BY_NAME[name]['inputSchema'])
            data = self.execute(name, args)
            data = redact_secrets(data)
            failed = isinstance(data, dict) and (data.get('success') is False or bool(data.get('error')) or data.get('status') == 'error')
            if isinstance(data, dict) and isinstance(data.get('result'), dict):
                failed = failed or data['result'].get('success') is False
            return result(data, failed)
        except (ToolError, ValueError, TypeError, OSError) as exc:
            return result(redact_secrets(str(exc)), True)
        except Exception:
            # Do not leak credentials, request headers, or tracebacks into stdout.
            print('Unexpected tool execution failure.', file=sys.stderr)
            return result('Unexpected tool execution failure. Check the MCP server stderr.', True)

    def handle(self, message):
        if not isinstance(message, dict) or not isinstance(message.get('method'), str):
            return self.rpc_error(message.get('id') if isinstance(message, dict) else None, -32600, 'Invalid request; send one JSON object per line (batches are unsupported).')
        if 'id' not in message:
            return None
        request_id = message['id']
        method = message['method']
        params = message.get('params', {})
        if method == 'tools/call':
            data = self.call_tool(params)
        elif method == 'initialize':
            version = params.get('protocolVersion') if isinstance(params, dict) else None
            data = {'protocolVersion': version if version in PROTOCOLS else '2025-06-18',
                    'capabilities': {'tools': {}},
                    'serverInfo': {'name': 'cloudycode-server-panel', 'version': '1.0.0'},
                    'instructions': 'Destructive tools act on real sites. Confirm destructive and server-changing operations with the user before calling them.'}
        elif method == 'ping':
            data = {}
        elif method == 'tools/list':
            data = {'tools': TOOLS}
        else:
            return self.rpc_error(request_id, -32601, 'Method not found: ' + method)
        return {'jsonrpc': '2.0', 'id': request_id, 'result': data}

    @staticmethod
    def rpc_error(request_id, code, message):
        return {'jsonrpc': '2.0', 'id': request_id, 'error': {'code': code, 'message': message}}


def main():
    try:
        server = MCPServer()
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    for line in sys.stdin:
        try:
            message = json.loads(line, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
        except ValueError:
            reply = server.rpc_error(None, -32700, 'Parse error: expected one JSON object per line.')
        else:
            reply = server.handle(message)
        if reply is not None:
            print(json.dumps(reply, ensure_ascii=False, allow_nan=False), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
