# On-behalf-of lab

The tool gateway allowlist answers whether this group may call `run_sql`. This lab answers the next question: after the call is allowed, does SQL see the person, or a bot service account?

It signs its own tokens with a lab secret. It does not call Entra, and it is not wired into `POST /v1/tools/invoke`.

## Run

From a clone of this repository, with the proxy package installed (`pip install -e rag-protection-proxy`, or `bash tools/setup_venv.sh`):

```bash
cd rag-protection-proxy
python -m rag_protection_proxy.tools_gateway.obo demo
```

Expected output:

```text
1. Alice (engineer) + run_sql  → expect BLOCK (group)
   Caller not authorized for tool run_sql
2. Frank (data-platform) + run_sql → expect ALLOW, acted_as_oid=frank-oid
   allow Tool invocation allowed with OBO user subject
   acted_as_oid= frank-oid rows= 3
3. App-only bot + run_sql → expect BLOCK (service account)
   app-only token: agent would call the API as a service account
4. Frank over-asks Files.ReadWrite.All for SQL → downscope empty / block
   downscope empty: agent requested scopes the tool policy does not allow
```

## What each line is

The command mints three lab tokens and calls one function four times. The first failed check wins.

Alice and Frank hold user tokens for the gateway (`api://agent-gateway`). Alice is in `engineering`. Frank is in `data-platform`. The bot token is app-only: client credentials, no person.

`run_sql` allows the group `data-platform`, the scope `SQL.Read`, and the audience `api://mock-sql`.

1. Alice stops at the group check. There is no exchange and no SQL.
2. Frank passes. The exchange keeps `frank-oid`, sets the audience to `api://mock-sql`, the grant to `obo`, and the scope to `SQL.Read`. SQL returns three payroll rows because `data-platform` sees the whole table. The stamp is `acted_as_oid=frank-oid`.
3. The app-only token stops before the group check. A robot that holds `Files.ReadWrite.All` is not exchanged.
4. Frank is still allowed to use the tool name. The exchange intersects `Files.ReadWrite.All` with `SQL.Read`. The overlap is empty, so the call stops.

A mail token presented to SQL is refused by the SQL stand-in because the audience does not match. The `demo` command does not print that case. `tests/test_obo_identity.py` covers it.

## Tests

```bash
cd rag-protection-proxy
python -m pytest tests/test_obo_identity.py -q
```

Optional session, recipient, and replay checks stay skipped unless you opt in:

```bash
RAG_OBO_EXERCISES=1 python -m pytest tests/test_obo_exercises.py -q
```

Code: `rag_protection_proxy/tools_gateway/obo/`.
