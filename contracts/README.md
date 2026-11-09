# HeadcountRegistry

Append-only record of Headcount report fingerprints on LitVM LiteForge, one per UTC day.
A day can be published once and never changed, so anyone can recompute a snapshot's digest and check it with `verify`.

```bash
cd contracts
forge test -vv
```

## Deploy

Use a Foundry keystore account, never a raw key on the command line.

```bash
cd contracts
cast wallet import headcount-deployer --interactive  # once
export LITEFORGE_RPC=https://liteforge.rpc.caldera.xyz/http
forge script script/Deploy.s.sol --rpc-url liteforge --account headcount-deployer --broadcast
```

`HEADCOUNT_OWNER` sets the publishing owner; it defaults to the deployer.
After deploying, set the repository variable `HEADCOUNT_REGISTRY` to the address and store the publisher's testnet key as the secret `REGISTRY_PUBLISHER_KEY`, so the daily scan publishes each fingerprint.
