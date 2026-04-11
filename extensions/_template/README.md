# Extension Template

Use this template as the starting point for any future external extension.

Category options:

- `export`
- `analysis`
- `integration`

Rules:

- import only from `core`
- read only through public read methods
- never read runtime JSON directly
- never write inside `.cerebro/`
- never turn extension output into canonical truth

If the design needs internal runtime paths or direct JSON access, stop and redesign.
