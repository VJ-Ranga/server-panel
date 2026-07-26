# README Documentation Design

## Goal

Create a GitHub-friendly `README.md` that explains what the Server Management Panel is, how to install it, how to run it, and how to use it to manage local WordPress and PHP-based projects.

## Audience

The README is for:

- The project owner using the panel as a local localhost management tool.
- GitHub visitors or future users who clone the repository.
- Developers who want a quick operational overview before reading the code.

It should not assume the reader already knows the project history.

## Tone And Style

- Clear, practical, and direct.
- Beginner-friendly for daily usage.
- Technical enough to explain sudo, services, project paths, and security boundaries.
- Concise enough to be useful as a front-page GitHub README.

## README Structure

Use this section order:

1. Project title and short description.
2. What the panel manages.
3. Requirements.
4. Installation.
5. First-time sudo setup.
6. Starting and stopping the panel.
7. Login and settings.
8. Daily usage with App Launcher.
9. App workflows:
   - WordPress.
   - Laravel.
   - CodeIgniter.
   - PHP Projects.
10. Server tools:
   - Dashboard.
   - Nginx.
   - MySQL.
   - phpMyAdmin.
   - Performance.
11. Important files.
12. Security notes.
13. Troubleshooting.
14. Development and verification commands.

## Required Content

The README must include:

- Default URL: `http://127.0.0.1:8765`.
- Default password: `admin`, with instruction to change it in Settings.
- First-time sudo setup command:

```bash
sudo bash ~/Documents/server-panel/setup-sudo.sh vjranga
```

- Start command:

```bash
cd ~/Documents/server-panel
python3 panel.py
```

- Stop command:

```bash
kill $(lsof -ti:8765)
```

- Clear warning that the panel is intended for local use and should not be exposed publicly.
- Explanation that App Launcher is the main app hub and app-specific pages are opened from Create/View All/Manage actions.
- Explanation that helper scripts perform privileged operations through narrow sudoers rules.
- Troubleshooting entries for port conflicts, Nginx config failures, MySQL socket auth, Composer missing, and phpMyAdmin access.

## Out Of Scope

- No screenshots in this change.
- No generated API reference table copied in full from `CLAUDE.md`.
- No installer automation changes.
- No code changes outside documentation.

## Self-Review

- Placeholder scan: no TBD or TODO items remain.
- Scope check: this is documentation only.
- Consistency check: commands and feature descriptions match `CLAUDE.md`.
- Ambiguity check: README is for users plus GitHub visitors, not only local private notes.
