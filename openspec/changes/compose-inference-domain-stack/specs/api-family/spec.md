## ADDED Requirements

### Requirement: A gateway in front of a model server is one family library

The family MUST provide one gateway library that fronts an OpenAI-style model
server behind the bearer gate: it reads the listing it fronts at startup and
takes the served model, the per-request charge, and the purchase pointer from
it, refusing to become ready on a card that is not request-priced; it reads
the request's `model` and refuses one the listing does not serve before any
charge; it verifies the key, calls a per-request verification hook that
admits everything until a proof format is configured, and only then charges
and forwards; it replaces the buyer's credential with the deployment's own
upstream credential, forwards streamed responses as they arrive, and lists
only the served model. A domain composes it in its own executable, supplying
the listing reference, the upstream, and the signing credential; the library
MUST import no domain.

#### Scenario: Two domains front model servers

- **WHEN** the inference gateway executable and an API-credits composition each
  wrap a model server with the library
- **THEN** both refuse an unlisted model uncharged, charge an admitted request
  once, and stream, differing only in the values each root supplies

#### Scenario: A domain is imported by the library

- **WHEN** the architecture check reads an import of a domain package from the
  gateway library
- **THEN** the check fails naming the import

#### Scenario: The published price and the configured charge disagree

- **WHEN** a gateway is started against a listing whose `request_credits` is
  not the amount an operator configured elsewhere
- **THEN** there is nothing to disagree with: the gateway charges the
  listing's `request_credits`, and a card with any non-zero per-token rate
  keeps the gateway from becoming ready

### Requirement: The gate verifies and charges in separable steps

The bearer gate MUST expose key verification separately from the charge, with
the same authority exchanges and cached state as its single authorize
operation, so a composition can run a check between a verified key and its
charge without charging a request it then refuses.

#### Scenario: A check between verification and charge refuses

- **WHEN** a composition verifies a key, runs its own check, and refuses
- **THEN** the key's balance is unchanged and the authority saw only the
  verification

### Requirement: A key is scoped to its first grant

The authority MUST bind a key to the service and resource of the grant that
created it and MUST refuse an existing-key issuance whose service or resource
differs, naming the refusal, so a key's one balance is only ever spent on what
every one of its grants bought.

#### Scenario: A key is topped up from another listing

- **WHEN** a buyer who holds a key issued for one listing purchases onto that
  key from a listing with a different service or resource
- **THEN** issuance is refused naming the key's scope, no grant is recorded,
  and the key's balance is unchanged
