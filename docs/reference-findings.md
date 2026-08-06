# Reference-project inspection

Inspection date: 2026-08-06

## Trustix

The local Trustix repository is a brownfield full-stack application with a root
Compose stack, a Django backend, two React Router frontends, PostgreSQL, Redis, Celery,
Playwright configuration, and a large `.claude` workflow submodule. Its Django backend
uses `core` plus root-level domain apps and decomposes settings by concern. Its AI layer
uses sequential phase documents, machine-readable manifests and blueprints, explicit
scope rules, deterministic quality-gate scripts, reusable skills, project memory,
artifact hashing, and convergence/stagnation concepts.

Useful conventions retained:

- spec-first, HTML-before-framework delivery;
- explicit phase and file-scope boundaries;
- deterministic gates around agentic tasks;
- reusable skill and stable-agent catalogs;
- cached project knowledge and artifact invalidation;
- split settings, root-level Django domain apps, PostgreSQL/Redis health ordering;
- typed frontend validation and Playwright browser checks.

Conventions intentionally not copied:

- hard-coded Compose database credentials and local container names;
- build output, virtual environments, caches, `.DS_Store`, logs, and duplicate frontend code;
- framework/version pins without a documented upgrade policy;
- deployment as an automatic final pipeline step;
- unbounded improvement loops;
- repository-specific payment, scraping, wallet, and tunnel configuration;
- any secrets or local-only settings.

## DRF_boilerplate

The GitHub reference has the recognizable layout requested by the specification:
`core/`, `user/`, project-level `media/` and `static/`, root `manage.py`, and
`.env.example`. The domain app owns models, serializers, views, URLs, permissions,
admin, and migrations.

The structural conventions are retained and expanded with services, selectors,
split tests, split settings, standard errors, OpenAPI, logging, request IDs, health
checks, and production settings as generation rules in the Django behavior pack.
The reference's Django 4.0.4, DRF 3.13.1, MySQL, minimal test structure, and realistic
committed secret are intentionally not copied. Agents choose supported framework
versions and production dependencies when generating the target monorepo, then lock
and independently verify them there.

Sources:

- https://github.com/imzulkar/DRF_boilerplate
- https://docs.djangoproject.com/en/dev/releases/6.0/
- https://www.django-rest-framework.org/community/release-notes/
- https://nextjs.org/blog/next-16
- https://nodejs.org/en/about/previous-releases
