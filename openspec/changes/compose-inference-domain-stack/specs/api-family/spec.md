## ADDED Requirements

### Requirement: A gateway in front of a model server is one family library

The family MUST provide one gateway library that fronts an OpenAI-style model
server behind the bearer gate: it reads the request's `model` and refuses one
the deployment does not serve before authorizing, authorizes and charges
through the gate inside the route, replaces the buyer's credential with the
deployment's own upstream credential, forwards streamed responses as they
arrive, lists only the configured model, and exposes a per-request
verification hook that admits everything until a proof format is configured.
A domain composes it in its own executable, supplying the served model name,
the charge, the upstream, and the signing credential; the library MUST import
no domain.

#### Scenario: Two domains front model servers

- **WHEN** the inference gateway executable and an API-credits composition each
  wrap a model server with the library
- **THEN** both refuse an unlisted model uncharged, charge an admitted request
  once, and stream, differing only in the values each root supplies

#### Scenario: A domain is imported by the library

- **WHEN** the architecture check reads an import of a domain package from the
  gateway library
- **THEN** the check fails naming the import
