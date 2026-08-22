# MCP Threat Alignment

This document maps the six threats unique to the Model Context Protocol (MCP)
ecosystem to the policy gates and agents in this repository, explaining
**what each threat is**, **which module(s) address it**, and **exactly how
the coverage is implemented**.

---

## The six MCP-specific threats

| # | Threat | Short definition |
|---|--------|-----------------|
| 1 | **Tool poisoning** | A malicious or modified tool is silently added to or changed in an agent's tool manifest, giving the agent dangerous new capabilities without human review. |
| 2 | **Rug-pull updates** | An MCP server package is installed without a pinned version; a later `latest`-tag update swaps in malicious code after the initial review. |
| 3 | **Confused deputy** | A high-privilege agent is manipulated (often via prompt injection from an untrusted data source) into performing an action on behalf of a lower-privilege caller that the caller could not perform directly. |
| 4 | **Token passthrough** | A secret credential (API key, token, password) is committed as a literal value in the MCP server config, leaking it to anyone who can read the file. |
| 5 | **Cross-server shadowing** | A malicious or compromised MCP server presents tool names or prompts that override, shadow, or poison the instructions supplied by a legitimate server in the same session. |
| 6 | **Over-broad scopes** | An MCP server or agent tool is given far more capability (filesystem write, shell exec, unrestricted network) than its declared purpose requires, violating least-privilege. |

---

## Coverage matrix

| Threat | Gate | Module | Policy file | How it is enforced |
|--------|------|--------|-------------|-------------------|
| Tool poisoning | **Gate 2** – Tool manifest diff | `policy_gate/tool_manifest.py` | `policies/tool_manifest_policy.yaml` `policies/tool_manifest_review_log.yaml` | Every `@tool`-decorated function is extracted via AST and diffed against a signed baseline. Any unclassified, newly-added, or signature-changed tool at a `high`/`critical` risk tier **fails the gate** unless a named human reviewer has logged a sign-off entry. |
| Rug-pull updates | **Gate 3** – MCP server vetting | `policy_gate/mcp_vetting.py` | `policies/mcp_server_allowlist.yaml` | All `npx`/`uvx` invocations must carry an explicit `@x.y.z` or `==x.y.z` version pin. Any unpinned invocation is a gate violation. The gate also enforces a command allowlist so only `python`, `python3`, `uvx`, `npx`, and `docker` can be used to launch servers. |
| Confused deputy | **Gate 1** – Prompt review | `policy_gate/prompt_review.py` | `policies/prompt_policy.yaml` `policies/prompt_review_log.yaml` | The assembled system prompt is checked for forbidden patterns (`ignore previous instructions`, jailbreak personas, blanket `never refuse` directives) that are classic vectors for confused-deputy attacks via prompt injection. The prompt is also diffed against a signed baseline so any change requires a named reviewer to sign off. |
| Token passthrough | **Gate 3** – MCP server vetting | `policy_gate/mcp_vetting.py` | `policies/mcp_server_allowlist.yaml` | Env-var keys matching `API_KEY`, `TOKEN`, `SECRET`, or `PASSWORD` must use `"${VAR_NAME}"` shell-expansion syntax; literal values are a gate violation. This prevents secrets from being committed to any `mcp.json`-style config. |
| Cross-server shadowing | **Gate 3** – MCP server vetting | `policy_gate/mcp_vetting.py` | `policies/mcp_server_allowlist.yaml` | Every server entry must carry a `trust_review` block (reviewer name, date, notes). Unreviewed servers are rejected outright. The allowlist further restricts remote server URLs to explicitly whitelisted domains (`localhost`/`127.0.0.1` by default), preventing a rogue remote server from injecting itself into the session. |
| Over-broad scopes | **Gate 2** – Tool manifest diff | `policy_gate/tool_manifest.py` | `policies/tool_manifest_policy.yaml` | Every tool must have an explicit `risk` tier (`low`/`medium`/`high`/`critical`) and a `justification`. No tool can ship without this classification. Tools like `run_command` (critical) and `write_text_file` (high) require a reviewer sign-off, creating a mandatory least-privilege audit trail. |

---

## Agent-by-agent coverage

### USEA agent (`profiles/usea.yaml`)

| Threat | Covered? | Notes |
|--------|----------|-------|
| Tool poisoning | ✅ | `baselines/usea/tool_manifest.baseline.json` is the signed baseline; `run_command` (critical) and `write_text_file` (high) both require sign-off. |
| Rug-pull updates | ✅ | `configs/usea.mcp.json` pins every server; Gate 3 rejects any unpinned `npx`/`uvx` entry. |
| Confused deputy | ✅ | `baselines/usea/system_prompt.baseline.txt` is the approved prompt text; forbidden injection patterns are enforced by `policies/prompt_policy.yaml`. |
| Token passthrough | ✅ | `configs/usea.mcp.json` uses `${VAR}` expansion for all credentials; any literal secret value in a new config fails Gate 3. |
| Cross-server shadowing | ✅ | Each server entry in `configs/usea.mcp.json` carries a `trust_review` block; only localhost/127.0.0.1 is whitelisted for remote URLs. |
| Over-broad scopes | ✅ | All USEA tools are classified in `policies/tool_manifest_policy.yaml`: `list_directory`/`read_text_file`/`recall_prior_prompts` → low; `write_text_file` → high; `run_command` → critical. |

### CrewAI agent (`profiles/crewai.yaml`)

| Threat | Covered? | Notes |
|--------|----------|-------|
| Tool poisoning | ✅ | `baselines/crewai/tool_manifest.baseline.json` is the signed baseline; `execute_python` (critical) requires sign-off. |
| Rug-pull updates | ✅ | `configs/crewai.mcp.json` must pin all server packages; Gate 3 enforces this identically to the USEA profile. |
| Confused deputy | ✅ | `baselines/crewai/system_prompt.baseline.txt` is the approved backstory; the same forbidden-pattern rules apply. |
| Token passthrough | ✅ | Gate 3 applies the same secret-expansion enforcement to `configs/crewai.mcp.json`. |
| Cross-server shadowing | ✅ | Each server entry in `configs/crewai.mcp.json` requires a `trust_review` block; domain allowlist is shared. |
| Over-broad scopes | ✅ | CrewAI tools are classified: `read_file`/`search_web` → low/medium; `execute_python` → critical (full code-execution, must be sandboxed per the justification note). |

---

## Architectural safeguards reinforcing all six threats

1. **Static analysis only.** Gates 1 and 2 parse agent files with Python's `ast`
   module and never `import` or `exec` them. A malicious tool or injected prompt
   cannot run code during the gate itself.

2. **Fail closed.** An unclassified tool, a missing baseline, an unsigned
   high-risk change, or an unreviewed server all produce a `fail` status
   rather than a silent `pass`. There is no "unknown = allowed" path.

3. **Profiles are the only repo-specific knowledge.** The gate engine is fully
   generic; `profiles/usea.yaml` and `profiles/crewai.yaml` are the only
   files that know each agent's file names and variable names. Adding a new
   governed agent requires only a new profile, new baselines, and new evals.

4. **Policies are reviewable YAML, not code.** Changing what is blocked or
   required is a normal, diffable pull request against this repo — not a
   hidden code change.

5. **CI enforcement.** The `stage-validation.yml` workflow runs `pytest` on
   every PR targeting `stage` or `main`. The test suite exercises both the
   pass path (compliant USEA/CrewAI fixtures) and the fail path (dedicated
   bad fixtures that prove every rule fires).

---

## Quick reference: which file to look at for each threat

| Threat | First file to read |
|--------|-------------------|
| Tool poisoning | `policy_gate/tool_manifest.py` → `policies/tool_manifest_policy.yaml` |
| Rug-pull updates | `policy_gate/mcp_vetting.py` → `policies/mcp_server_allowlist.yaml` (key: `require_pinned_version`) |
| Confused deputy | `policy_gate/prompt_review.py` → `policies/prompt_policy.yaml` (key: `forbidden_patterns`) |
| Token passthrough | `policy_gate/mcp_vetting.py` → `policies/mcp_server_allowlist.yaml` (key: `secret_env_key_patterns`) |
| Cross-server shadowing | `policy_gate/mcp_vetting.py` → `policies/mcp_server_allowlist.yaml` (keys: `require_trust_review`, `allowed_remote_domains`) |
| Over-broad scopes | `policy_gate/tool_manifest.py` → `policies/tool_manifest_policy.yaml` (key: `review_required_risk_tiers`) |
