# Deployment and recovery

Run commands from `backend/` unless stated otherwise. The checked-in config targets the existing CHEMI account resources. Change the IDs and route before using another account.

## Account prerequisites

The current OAuth login can deploy Workers and manage D1, AI, and Vectorize. It cannot create user API tokens. R2 currently requires dashboard activation.

From the repository root, run the human setup wizard:

```bash
bash backend/scripts/setup-cloudflare.sh
```

It opens R2 activation and API-token creation. It captures the deployment token without echoing it, stores a local ignored credential file, and sets the GitHub repository secrets. Review the token scope before creating it. Keep account permissions limited to the CHEMI account and zone permissions limited to `quangiz.me`.

The deploy workflow needs Workers deployment permissions and access to D1, Vectorize, Workers AI, and R2. Token permission labels can change. Use the [Cloudflare token guide](https://developers.cloudflare.com/fundamentals/api/get-started/create-token/) and [GitHub Actions deployment guide](https://developers.cloudflare.com/workers/ci-cd/external-cicd/github-actions/).

## Resources

D1 `chemi` and Vectorize `chemi-knowledge` already exist. To recreate resources in a new account:

```bash
npx wrangler login
npx wrangler d1 create chemi
npx wrangler vectorize create chemi-knowledge --dimensions 768 --metric cosine
npx wrangler r2 bucket create chemi-artifacts
```

Copy the new D1 ID into `wrangler.jsonc`. After R2 activation and bucket creation, enable the `ARTIFACTS` binding by uncommenting `r2_buckets`.

Set application and provider secrets through standard input prompts:

```bash
npx wrangler secret put OPENROUTER_API_KEY
npx wrangler secret put API_KEYS
```

`SERPAPI_KEY` is optional. PubChem structure lookup works without it. Do not put a deployment token in Worker secrets.

## Knowledge and release

```bash
npx wrangler d1 execute chemi --remote --file schema.sql
CLOUDFLARE_ACCOUNT_ID=4afef0260494c77c6f15bff3e1df489d uv run python scripts/build_knowledge.py --remote
uv run pywrangler deploy
bash smoke.sh https://chemi.quangiz.me
```

The ingestion script uses `CLOUDFLARE_API_TOKEN` when set. Locally, it can obtain the existing Wrangler OAuth token without printing it. Vectorize mutations become visible asynchronously. The script replaces the lexical corpus after vector submission. Removed vector IDs can remain in the index, but retrieval only accepts IDs with current D1 text. A larger corpus needs a versioned ingestion process and stale-vector cleanup.

The smoke script checks `/health` and D1 connectivity through `/ready`. Also verify a real authenticated query, source citations, a follow-up turn, quiz data, an image, and audio. The basic smoke check does not cover these features. Run the full checker separately:

```bash
uv run python scripts/check_live.py --full
# After R2 activation:
uv run python scripts/check_live.py --full --audio
```

This command makes real model calls and consumes the application rate limit.

## Access and logs

The browser requires an application access key in production. The current local copy is in the ignored `.dev.vars` file. Configure one key per caller identity when isolation is needed.

```bash
npx wrangler tail
```

Each request emits a JSON access record and returns `X-Request-ID`. Logs omit request bodies, access keys, and provider keys.

## Rollback

```bash
npx wrangler deployments list
npx wrangler rollback <known-good-version-id>
bash smoke.sh https://chemi.quangiz.me
```

A rollback changes the Worker version, not D1 data. Use additive migrations. Keep resources used by the previous version available. After recovery, fix forward through the normal checks.

## Remaining production limits

- The corpus has six short notes. Expand it before claiming broad curriculum coverage.
- The small evaluation set does not measure production answer accuracy.
- A valid citation ID does not prove that the cited text supports every claim.
- Generated quizzes need factual quality evaluation beyond schema validation.
- API keys are caller-group access, not individual user accounts.
- Streaming, artifact expiration, and production latency distributions remain future improvements.

The Cloudflare rate limiter is per-location and eventually consistent. It is not a strict global billing quota. See the [rate-limit documentation](https://developers.cloudflare.com/workers/runtime-apis/bindings/rate-limit/).
