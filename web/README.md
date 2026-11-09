# Headcount site

Static Next.js site built from the snapshots in `../snapshots`.
Every page is generated at build time, so `pnpm build` writes a static site to `out/`.

```bash
cd web
pnpm install
pnpm dev     # http://localhost:3000
pnpm build   # static export to out/
```

`NEXT_PUBLIC_HEADCOUNT_REGISTRY` shows the registry address and a `cast` check on the method page once the contract is deployed.
