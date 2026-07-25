# CodeIgniter 4 Support Design

## Goal

Add CodeIgniter 4 app management to the local server panel. The user can create, view, open, and delete local CodeIgniter 4 apps from the panel using the same workflow style as the existing Laravel section.

## Scope

- Support CodeIgniter 4 only.
- Create new apps with Composer using `codeigniter4/appstarter`.
- Detect existing CodeIgniter 4 apps in `/var/www`, `/opt`, and one nested `/opt/*/*` level.
- Manage Nginx virtual hosts for local ports.
- Create and delete the app database and database user.
- Do not support CodeIgniter 3 creation or migration in this version.

## Backend Changes

- Add CodeIgniter app discovery by scanning for the `spark` file.
- Read `.env` values for app URL and database credentials using the existing `.env` parsing helpers.
- Add install and delete background jobs following the Laravel job pattern.
- Add API routes:
  - `GET /api/codeigniter/apps`
  - `GET /api/codeigniter/next_port`
  - `POST /api/codeigniter/install`
  - `GET /api/codeigniter/install/<job_id>`
  - `DELETE /api/codeigniter/apps`
  - `GET /api/codeigniter/delete/<job_id>`
  - `POST /api/codeigniter/port`
- Use the existing MySQL helper flow so root socket authentication and saved MySQL credentials continue to work.

## Helper Script

Add `codeigniter-helper.sh` for privileged operations:

- Copy Composer-created source files into the final install path.
- Set ownership and permissions for the app files.
- Keep writable directories writable for PHP-FPM.
- Create an Nginx site whose root is `<install_path>/public`.
- Enable the site, validate with `nginx -t`, then reload or start Nginx.
- Delete the app files and Nginx site.
- Change the Nginx listen port safely.

The helper will use the same path and site-name safety checks as `laravel-helper.sh`.

## Install Flow

1. Validate site name, install path, database name, database user, database password, and port.
2. Verify Composer is installed.
3. Run `composer create-project codeigniter4/appstarter` into a temporary source directory.
4. Create the MySQL database and user.
5. Write `.env` with local app and database settings:
   - `CI_ENVIRONMENT = development`
   - `app.baseURL = http://localhost:<port>/`
   - `database.default.hostname = 127.0.0.1`
   - `database.default.database = <db_name>`
   - `database.default.username = <db_user>`
   - `database.default.password = <db_pass>`
   - `database.default.DBDriver = MySQLi`
6. Install files and Nginx config through `codeigniter-helper.sh`.
7. Show the app URL and created credentials in the install result.

On failure, the job rolls back anything it created: database user, database, app files, and Nginx site.

## UI Changes

- Add a sidebar item for CodeIgniter under Services.
- Add a CodeIgniter page with two tabs:
  - Installed Apps
  - Create New App
- Installed Apps shows app name, path, app URL, database name, database user, Nginx site, port, and actions.
- Actions include open app, open phpMyAdmin, change port, and delete.
- Create New App form follows the Laravel form structure:
  - app name
  - install path
  - port
  - database name
  - database user
  - database password with generate button
  - live install log

## Sudoers

Update `setup-sudo.sh` to allow passwordless sudo for `codeigniter-helper.sh` with arguments, matching the Laravel helper rule style.

## Error Handling

- Composer missing: show a clear install error.
- Invalid input: fail before creating resources.
- Nginx validation failure: stop install and roll back.
- MySQL errors: stop install and roll back created resources.
- Delete failures: show the helper output in the delete progress log.

## Testing

- Run Python syntax validation for `panel.py`.
- Verify the frontend has no obvious JavaScript syntax errors by loading the panel manually.
- Create a CodeIgniter 4 app on a free local port.
- Verify the app opens at `http://localhost:<port>`.
- Verify the app appears in Installed Apps after refresh.
- Verify phpMyAdmin link uses the detected database name.
- Change the app port and verify Nginx reloads and the new URL works.
- Delete the app and verify files, Nginx site, database, and database user are removed.
