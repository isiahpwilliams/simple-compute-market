## ADDED Requirements

### Requirement: A gateway in front of a model server is one family library

The family MUST provide one gateway library that fronts an OpenAI-style model
server behind the bearer gate. It consumes one family-owned offering value
— the service name it admits, the key scope it enforces, a default
per-request charge, the purchase pointer, the upstream and its credential
reference, and the current canonical terms as verification input — which the
composing domain's executable projects from its own validated listing; the library MUST import no domain and MUST NOT
read a listing itself. It reads the request's `model` and refuses one the
offering does not serve before any charge; it verifies the key against the
offering's scope, calls a per-request verification hook with the offering's
current canonical terms and the key's accepted terms payload and digest as
verification returned them, which admits everything until a proof format is
configured, and only then charges the key's verified charge, or the
offering's default when verification returns none, and forwards; it replaces
the buyer's credential with the deployment's own upstream credential,
forwards streamed responses as they arrive, and lists only the served model.

#### Scenario: Two domains front model servers

- **WHEN** the inference gateway executable and an API-credits composition each
  wrap a model server with the library
- **THEN** both refuse an unlisted model uncharged, charge an admitted request
  once, and stream, differing only in the values each root supplies

#### Scenario: A domain is imported by the library

- **WHEN** the architecture check reads an import of a domain package from the
  gateway library
- **THEN** the check fails naming the import

#### Scenario: The seller reprices after a sale

- **WHEN** a key was issued under a listing charging one credit per request,
  the seller republishes the listing at ten, and the gateway is restarted
- **THEN** requests on that key are charged one credit, a key issued after the
  republication is charged ten, and a top-up of the first key from the
  repriced listing is refused

### Requirement: The gate verifies and charges in separable steps

The bearer gate MUST expose key verification separately from the charge, with
the same authority exchanges and cached state as its single authorize
operation, so a composition can run a check between a verified key and its
charge without charging a request it then refuses.

#### Scenario: A check between verification and charge refuses

- **WHEN** a composition verifies a key, runs its own check, and refuses
- **THEN** the key's balance is unchanged and the authority saw only the
  verification

### Requirement: The public-result extension receives the delivery's settlement context

The selling library MUST call a domain's public-result extension with the
accepted listing resource, the secret-free issuance result, and a delivery
context naming the agreed settlement mechanism and the settlement stage's
reference, so a domain whose public record is the family's materialization can
build it from the extension's inputs alone. A domain that supplies no
extension MUST see no change to its delivery.

#### Scenario: A domain builds its materialization in the extension

- **WHEN** a storefront's bundle supplies a public-result extension and a
  delivery completes from verified Alkahest evidence
- **THEN** the extension receives the mechanism and the escrow uid beside the
  listing and the result, and the public result carries what it returns

#### Scenario: API credits delivers without an extension

- **WHEN** the API-credits storefront, which supplies no extension, completes
  a delivery
- **THEN** its public result is byte-identical to the result before the
  context existed

### Requirement: The issuance subject may carry accepted terms

The family issuance subject MAY carry the accepted terms as canonical JSON,
their digest, and a per-request charge, which the domain's projection reads
from the accepted listing; the charge is an integer from one to the ledger's
signed 64-bit maximum, the range the authority can consume. When present, the digest and charge MUST enter the
issuance request digest and the signed evidence, the authority MUST verify the
digest against the payload and record all three in a table of its own beside
the grant, leaving the grant table's columns unchanged, and `verify` MUST
return the key's pinned terms, digest, and charge; when absent, they MUST be
omitted rather than serialised as null, so digests, evidence, and `verify`
are byte-identical to their form before the fields existed.

#### Scenario: API credits issues without terms

- **WHEN** an API-credits issuance request, which sets neither value, is
  digested and its key verified
- **THEN** the digest, the evidence, and the verify response match the
  recorded pins byte for byte

#### Scenario: The authority is upgraded and rolled back

- **WHEN** the new authority image starts against a database its previous
  image wrote, and the previous image is later started against the result
- **THEN** the migration creates the terms table, existing grants read as
  unpinned, and the previous image starts and serves, since the grant table
  it checks is unchanged

#### Scenario: Metering reads the accepted card

- **WHEN** a later consumer prices a request against a grant issued with
  accepted terms
- **THEN** the authority supplies the grant's full accepted terms, verified
  against their digest, without consulting the storefront

### Requirement: A key is scoped to its first grant

The authority MUST bind a key to the service, resource, and accepted terms
digest of the grant that created it and MUST refuse an existing-key issuance
whose service, resource, or terms differ, naming the refusal, so a key's one
balance is only ever spent on what every one of its grants bought, at the
charge each was bought at. `verify` and `consume` MAY carry the caller's
expected service and resource; when present, the authority MUST refuse a key
whose first grant's scope differs, uncharged, with a named status, and when
absent it MUST behave as before the fields existed.

#### Scenario: A key is topped up from another listing

- **WHEN** a buyer who holds a key issued for one listing purchases onto that
  key from a listing with a different service or resource
- **THEN** issuance is refused naming the key's scope, no grant is recorded,
  and the key's balance is unchanged

#### Scenario: A key is presented at another offering's gateway

- **WHEN** a funded key issued for one service and resource is presented to a
  gateway whose offering names another, under the same authority
- **THEN** the authority refuses the verification by scope, the gateway
  answers `403`, the model server receives nothing, and the key's balance is
  unchanged
