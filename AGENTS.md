# Repository guidance

## Commands and environment
- Run commands from the repository root. In Windows PowerShell, use `.\venv\Scripts\python.exe` directly; activation is unnecessary.
- The existing venv has Python 3.13.7, Django 6.1, and mysqlclient 2.3.0. The generated settings header says Django 5.2.6; it does not describe the installed version. There is no dependency manifest or lockfile.
- System check: `.\venv\Scripts\python.exe manage.py check`.
- Database setup: `.\venv\Scripts\python.exe manage.py migrate`; then start development with `.\venv\Scripts\python.exe manage.py runserver`.
- Tests: `.\venv\Scripts\python.exe manage.py test main`. Focused example: `.\venv\Scripts\python.exe manage.py test main.tests.PublicationTests.test_hidden_entries_cannot_be_opened_directly`.
- `config/settings.py` uses MySQL database `djan` at `localhost:3306`; the root `db.sqlite3` is not used. Local settings load from ignored `.env`; process environment takes precedence. Dependencies are pinned in `requirements.txt`. Database-backed commands require MySQL; Django tests also require permission to create a test database.

## Wiring and frontend
- `config/urls.py` mounts `main.urls` at the root and Django admin at `/admin/`. `/`, `/main` (name `start`), and `/home` share the homepage. Many public routes deliberately have no trailing slash; use their existing route names. Legacy route names `prod`, `myform`, and `obr_result` resolve to `/how-we-play`, `/join`, and `/join/result`.
- Public pages inherit `main/templates/base.html`. Root `templates/` takes precedence over app templates and contains the admin override `templates/admin/base_site.html`.
- Active public CSS is `main/static/css/style.css` → `glass.css` → `atelier.css`, in that cascade order; later files override earlier styling. `main/templates/main/css/style.css` is not the stylesheet loaded by the base template.
- The public base loads `main/static/js/effects.js`; `atelier.js` is not loaded there. Admin styles are separate, under `main/static/main/`, connected through `main/admin.py` and the admin template override.

## Domain details that are easy to misread
- News and diary share `Publication`, distinguished by `kind`. Both lists and detail pages use `Publication.objects.published()` to exclude drafts and future-dated entries. Lists paginate at nine entries; editing happens in Django admin.
- Publication bodies are plain text rendered with `linebreaks` and autoescaping. `main/tests.py` checks paragraph rendering and HTML escaping as well as visibility, pagination, and admin editing.
- `main.models.User` is a contact record, not the authentication user; admin login uses Django's built-in user model.
- In the recruitment form, legacy `FormResult.step` means MMR and `gender` means Dota position. The form posts to `obr_result`; empty optional numeric/date fields are saved as `None`.
- `Product.sale` is the price, and `cat_id` is the ForeignKey field name (used as `select_related("cat_id")`). Seasonal filtering compares `Category.name` with Russian `зима`/`лето`, not `Category.category`.
- Migrations `0006` and `0007` update photo URLs on existing products; they do not seed a fresh catalog. Product photos are remote URLs with a separate source URL, not uploaded media files.

## Community features and demo data
- Game planning routes live in `main/journeys.py`; timezone middleware uses the profile's IANA zone (Moscow fallback). Structured `play_days` are strings `0`–`6`, with local `play_from`/`play_until`; overlap handles midnight. Accept/remove actions invalidate scheduled games and participant confirmations.
- OpenDota import is explicit via report permission or `import_match`; it keeps manual report content and stores only selected statistics. Backups include a SHA-256 sidecar; `verify_backup` performs a read-only integrity check.
- `SHOWCASE.md` contains the end-to-end presentation flow. `seed_demo --refresh` maintains a completed cup, an ongoing cup, and an upcoming cup with open registration; dates are relative to the run.
- Match reports link to profiles through `MatchReport.players` and to a bracket series through `tournament_match`. Team profiles use `TournamentTeam.players`; the plain-text roster remains the record of names, roles, and heroes. Public links must check both `is_active` and `is_public`.
- Hero portraits use Valve CDN URLs with internal names in `main/heroes.py`, verified against OpenDota. Unknown hero names render as text. Public feature CSS overrides live in `main/static/css/community.css`, loaded after atelier.
- New public feature views live in `main/community.py`; existing page views remain in `main/views.py`.
- `Person.is_public` is visitor-controlled profile visibility; `is_active` remains admin-controlled. Both must hold for public profiles.
- Event registrations use `is_waiting`; cancellation locks the event and promotes the oldest waiting registration.
- A party has one captain position and up to four accepted responses on distinct positions. Accept and remove actions lock the listing.
- Use `main.services.change_order_status` for order status transitions. Cancellation restores stock once; reopening cancelled orders is rejected. Direct queryset status updates bypass this behavior.
- Password reset defaults to console email locally. SMTP variables are documented in `.env.example` and `DEPLOYMENT.md`.
- `manage.py seed_demo` adds marked fictitious data only with DEBUG enabled. It is repeatable and preserves existing rows. Generated demo credentials are stored only in ignored `.local/demo_accounts.json`.
- Additional tests: `manage.py test main.test_features`. Rate limits persist in `FormThrottle` and use REMOTE_ADDR without trusting forwarded headers.

## Support chat
- `start_support.bat` runs checks, migrations, and the development server. Support works locally without Telegram credentials or a worker. Operators reply at `/admin/main/supportconversation/` using Django admin accounts.
- The custom `SupportConversationAdmin.change_view` displays the chat instead of a model form. View permission permits reading; change permission permits replying. The inbox marks conversations whose latest message is from a visitor as awaiting a reply.
- Admin chat actions clear history or close/reopen the conversation; closed chats reject new messages. Clearing increments `SupportConversation.revision` so polling clients reset their displayed history. Operator message colors use the server-side `SupportMessage.COLORS` palette.
- `/support/messages` uses Django sessions and CSRF, not client-supplied conversation IDs. Visitor and admin chats poll every three seconds while visible; the admin inbox reloads every 15 seconds. Focused tests: `.\venv\Scripts\python.exe manage.py test main.test_support`.
- Legacy Telegram commands remain available but are not started by the bat file. Their secrets live in ignored `.local/telegram.json` or `TELEGRAM_BOT_TOKEN` / `TELEGRAM_SUPPORT_CHAT_ID`; never expose these to frontend code.
