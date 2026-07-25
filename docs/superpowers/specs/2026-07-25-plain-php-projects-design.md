# Plain PHP Projects Design

## Goal

Add plain PHP project management to the local server panel. The user can create and manage simple PHP projects with or without a MySQL database, using the same local Nginx, PHP-FPM, MySQL, and auto-port workflow as the existing WordPress, Laravel, and CodeIgniter sections.

## Scope

- Add a new **PHP Projects** section to the sidebar.
- Support panel-created plain PHP projects only for reliable discovery and safe deletion.
- Support three starter templates:
  - `blank`: creates the project folder and Nginx site only.
  - `php`: creates a working `index.php` with project name and PHP environment summary.
  - `php_db`: creates `index.php` and `config.php` with a MySQL connection test.
- Database creation is optional and only enabled for `php_db` projects.
- Auto-suggest the next available port starting from `8300`.
- Do not add Composer, framework scaffolding, or external dependencies for plain PHP projects.

## Project Metadata

Each panel-created PHP project gets a metadata file at:

```text
<install_path>/.server-panel-project.json
```

The metadata stores:

- project type: `php`
- project name
- template
- install path
- Nginx site name
- port
- database name, user, and whether the database was created by the panel
- creation timestamp

Discovery uses this metadata file instead of guessing from arbitrary PHP files. This avoids treating WordPress, Laravel, CodeIgniter, or unrelated folders as plain PHP projects.

## Backend Changes

- Add PHP project discovery by scanning for `.server-panel-project.json` in `/var/www`, `/opt`, and `/opt/*/*`.
- Add install and delete background jobs following the Laravel and CodeIgniter job pattern.
- Add API routes:
  - `GET /api/php-projects/apps`
  - `GET /api/php-projects/next_port`
  - `POST /api/php-projects/install`
  - `GET /api/php-projects/install/<job_id>`
  - `POST /api/php-projects/port`
  - `DELETE /api/php-projects/apps`
  - `GET /api/php-projects/delete/<job_id>`
- Reuse the existing MySQL helper flow so root socket authentication and saved MySQL credentials continue to work.

## Helper Script

Add `php-project-helper.sh` for privileged operations:

- Create the install directory.
- Copy generated template files from a temporary source directory.
- Set ownership and permissions for PHP-FPM.
- Create an Nginx site with root set to `<install_path>`.
- Enable the site, validate with `nginx -t`, then reload or start Nginx.
- Delete the app files and Nginx site.
- Change the Nginx listen port safely.

The helper uses the same path and site-name safety checks as the Laravel and CodeIgniter helpers.

## Install Flow

1. Validate project name, install path, template, port, and optional database fields.
2. If template is `php_db`, create the MySQL database and user.
3. Generate template files into a temporary source directory:
   - `blank`: only metadata.
   - `php`: `index.php` and metadata.
   - `php_db`: `index.php`, `config.php`, and metadata.
4. Install files and Nginx config through `php-project-helper.sh`.
5. Show the project URL and database credentials in the install result when applicable.

On failure, the job rolls back anything it created: database user, database, app files, and Nginx site.

## Templates

### Blank

- Creates only the project directory and `.server-panel-project.json`.
- Suitable when the user wants to place their own PHP files manually.

### PHP Only

- Creates `index.php`.
- The page shows:
  - project name
  - PHP version
  - server time
  - document root
- No database files are created.

### PHP + DB

- Creates `config.php` with MySQL credentials.
- Creates `index.php` that requires `config.php` and tests a PDO MySQL connection.
- The page clearly shows whether DB connection succeeded or failed.

## UI Changes

- Add a sidebar item for **PHP Projects** under Services.
- Add a page with two tabs:
  - Installed Projects
  - Create New Project
- Create New Project form includes:
  - project name
  - install path
  - template selector: Blank, PHP Only, PHP + DB
  - port
  - database name, database user, and database password fields shown only for PHP + DB
  - live install log
- Installed Projects shows:
  - project name
  - template
  - path
  - Nginx site
  - port
  - database info when available
  - actions: open site, open folder, phpMyAdmin when DB exists, change port, delete

## Sudoers

Update `setup-sudo.sh` to allow passwordless sudo for `php-project-helper.sh` with arguments, matching the Laravel and CodeIgniter helper rule style.

## Error Handling

- Invalid input fails before creating resources.
- MySQL errors stop install and roll back created resources.
- Nginx validation failure stops install and rolls back.
- Missing metadata during delete prevents accidental deletion of arbitrary folders.
- Delete removes the database and user only when metadata confirms the panel created them.

## Testing

- Run Python syntax validation for `panel.py`.
- Run backend unit tests for project discovery, metadata parsing, and route registration.
- Run frontend structure tests for sidebar, page fields, template selector, and JS routes.
- Run shell syntax validation for all helper scripts.
- Run frontend JavaScript syntax validation by extracting the inline script and checking it with Node.
- Manually create one project for each template and verify Nginx loads the expected URL.
- Verify PHP + DB project creates a database and shows a successful connection test.
- Verify port change updates Nginx and the new URL works.
- Verify delete removes files, Nginx site, and database resources only for DB-backed projects.
