## Summary

<!-- What does this PR change and why? -->

## Checklist

- [ ] Tests pass locally: `uv run python manage.py test apps`
- [ ] Lint passes locally: `uv run black --check .`, `uv run isort --check-only .`,
      `uv run flake8 --select=TMS010,TMS011,TMS012,TMS013,TMS020,TMS021,TMS022 apps/ config/ manage.py`
- [ ] `uv run pip-audit` has no new findings (or they're noted below)
- [ ] Model changes include a migration (`uv run python manage.py makemigrations`)
- [ ] `docs/CRUD.md` / `docs/STRUCTURE.md` updated if this
      changes models, views, permissions, or major features
- [ ] Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/)
      (`feat:`, `fix:`, `docs:`, `test:`, etc.)
- [ ] No secrets, `.env`, or `db.sqlite3` changes included

## Test plan

<!-- How did you verify this? New/updated tests, manual steps, screenshots for UI changes. -->
