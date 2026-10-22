## ADDED Requirements

### Requirement: Inference roles are composed from independent distributions

The inference domain MUST be served by four roles, each an independently
installable distribution: a storefront that publishes model-card listings,
negotiates, verifies settlement, and requests issuance; an authority that holds
keys, grants, balances, and the quota ledger; a gateway that admits requests to
a model server; and a buyer plugin that discovers, negotiates, and settles. The
storefront and buyer plugin MUST register through the market-domain entry
points under the identity `inference`. No inference distribution may import an
API-credits distribution.

#### Scenario: Roles are installed

- **WHEN** the inference storefront and buyer distributions are installed from
  built wheels
- **THEN** each registers the `inference.v1` contract once under its entry-point
  group and loads without any API-credits distribution present

#### Scenario: A sibling domain is imported

- **WHEN** an inference module imports an API-credits module, including under
  `TYPE_CHECKING`
- **THEN** the boundary test fails naming the import

### Requirement: Alkahest is the only inference settlement mechanism

The inference storefront and buyer plugin MUST compose exactly one settlement
mechanism, `alkahest.v1`, and MUST NOT depend on the fiat payments
(`arkhai.payments.v1`) distribution. A configuration naming any other mechanism MUST be refused at
startup rather than ignored.

#### Scenario: Another mechanism is configured

- **WHEN** a storefront configuration's settlement priority names a mechanism
  other than `alkahest.v1`
- **THEN** startup fails naming that mechanism before any request is served

#### Scenario: Role wheels are inspected

- **WHEN** the inference role wheels' requirements are read
- **THEN** none requires the fiat payments distribution

### Requirement: Issuance identifiers are inference-labelled and agree across the boundary

Inference issuance requests, results, evidence, and portable fulfillment
references MUST carry `inference` labels distinct from every other domain's, and
the storefront's issuance client and the authority MUST derive the same request
digest for the same request. Issued key identifiers MUST be distinguishable from
another domain's.

#### Scenario: The same request is digested on both sides

- **WHEN** a fixed issuance request is digested by the issuance client and by
  the authority
- **THEN** both produce the same bytes, and those bytes differ from the
  API-credits digest of the equivalent request

#### Scenario: A key is issued

- **WHEN** the inference authority issues a key
- **THEN** its identifier carries the inference prefix

### Requirement: Inference state is isolated

The inference authority and storefront MUST each persist to their own database,
shared with neither each other nor any other domain's services. An inference
key MUST NOT be accepted by another domain's authority, and another domain's key
MUST NOT be accepted by the inference authority.

#### Scenario: The stack is stood up beside API credits

- **WHEN** the inference and API-credits stacks run together
- **THEN** each authority and storefront uses an independent volume and no key
  issued by one authority verifies at the other

### Requirement: Bearer credential is delivery, not identity or payment authority

The inference domain MUST treat the marketplace principal that negotiates and
pays, the bearer credential that admits a request, and any authority that
authorizes spending as three separate identities. A bearer credential MUST admit
requests only against its own grant's balance and MUST NOT be accepted as
authorization to negotiate, purchase, top up another key, or authorize a charge
outside its grant.

#### Scenario: Bearer credential is presented to a market operation

- **WHEN** a bearer credential is offered as the credential for a negotiation,
  purchase, or top-up
- **THEN** the operation is refused as unauthenticated rather than treated as
  the key owner's marketplace signature

### Requirement: Quota-backed publication

An inference listing MUST identify an authoritative quota resource at a
configured site, and publication MUST require that resource to exist with
available credits. Reconciliation MUST close an open listing when authoritative
availability reaches zero and MAY reopen it when availability later becomes
positive; an unavailable authority MUST preserve the last complete listing state
rather than be read as zero.

The declared quota is a sales cap, not capacity. An inference listing MUST carry
the backed value of the declared backing property; a listing MUST NOT change
backing in place, and admitting the unbacked value is a filter-specification
version change.

#### Scenario: Seller declares no sellable quantity

- **WHEN** a seller submits an inference listing candidate with no quota resource
  or a zero declared quantity
- **THEN** publication is refused, because version 1 admits only the backed
  value, and the seller declares a cap instead

#### Scenario: Declared credits are sold out and later replenished

- **WHEN** reconciliation observes zero available credits for an open listing and
  later observes a positive quantity
- **THEN** it closes the listing and subsequently republishes it from the new
  authoritative view

### Requirement: The materialization pins the rate card at acceptance

On issuance the storefront MUST deliver a materialization carrying the rate card
of the listing the accepted negotiation was made against, as stored when the
negotiation was accepted. Republishing the listing MUST NOT change a
materialization already determined.

#### Scenario: The seller reprices between acceptance and fulfillment

- **WHEN** a negotiation is accepted and the seller republishes the listing with
  a different rate card before fulfillment completes
- **THEN** the materialization carries the rate card in force at acceptance

### Requirement: Only request-priced rate cards are publishable without metered consumption

While the gateway charges a fixed amount on admission, the storefront MUST
refuse to publish a listing whose rate card has a non-zero prompt, cached-prompt,
completion, or image rate, and the gateway's charge per admitted request MUST
equal the published `request_credits`. A published price MUST be one the seller
charges.

#### Scenario: A per-token rate card is configured

- **WHEN** a seller configures a listing whose rate card has a non-zero
  completion rate
- **THEN** publication is refused naming that field and nothing is published

#### Scenario: A request-priced listing is consumed

- **WHEN** a buyer makes a successful request against a listing priced at one
  credit per request
- **THEN** the key's balance falls by exactly one credit

### Requirement: The gateway admits only paid requests for listed models

The gateway MUST expose chat completions and completions in the OpenAI
version-1 style and MUST forward a request only after the authority has
verified the bearer credential and charged it. A request naming a model the
gateway does not serve MUST be refused before any charge. The gateway MUST
answer `401` for a missing or unknown credential, `403` for a revoked one, and
`402` with a pointer to where credits can be bought for an exhausted one. A
gateway MUST serve exactly one model at one configured charge, and its model
list MUST contain only that model.

#### Scenario: A request names an unlisted model

- **WHEN** a request with a valid, funded key names a model the gateway does not
  serve
- **THEN** the gateway answers `404`, the model server receives nothing, and the
  key's balance is unchanged

#### Scenario: A key is exhausted

- **WHEN** a request arrives on a key with no remaining credits
- **THEN** the gateway answers `402` with the storefront and registry where more
  can be bought, and the model server receives nothing

#### Scenario: A buyer tops up

- **WHEN** a buyer purchases more credits onto an exhausted key
- **THEN** a subsequent request on that key is admitted

### Requirement: The buyer's credential stops at the gateway

The gateway MUST NOT forward the buyer's bearer credential to the model server.
A credential the model server requires MUST be the gateway's own, supplied from
a mounted secret.

#### Scenario: A request is proxied

- **WHEN** an admitted request is forwarded
- **THEN** the model server receives no `Authorization` value supplied by the
  buyer

### Requirement: Streaming responses are forwarded unbuffered

The gateway MUST forward a streamed response to the buyer as it arrives and
MUST NOT hold it until the model server finishes.

#### Scenario: A completion is streamed

- **WHEN** a buyer requests a streamed completion
- **THEN** the first event reaches the buyer before the model server has sent
  the last

### Requirement: The buyer plugin discovers by model card under the inference schema

The inference buyer plugin MUST declare the `inference` schema identity and
MUST query only registries declaring it. It MUST offer discovery filters for
model, model family, quantization, modality, supported parameter, provenance,
minimum context length, and the rate bounds, compiled from the registry's
served filter specification, and MUST resolve the rate-bound co-requirement
from that specification rather than from code, refusing an unpaired bound
before sending it. A completed purchase MUST give the buyer the key, the
gateway base URL, and the served model name.

#### Scenario: A buyer searches by model

- **WHEN** a buyer lists inference offers for a `model_id` with a compute
  registry, an API-credits registry, and an inference registry configured
- **THEN** only the registry declaring the `inference` schema is queried and
  only listings for that model are returned

#### Scenario: Buyer bounds a rate without naming an asset

- **WHEN** a buyer asks the plugin for a rate bound and no `rate_card_asset`
- **THEN** the plugin, compiling against the served specification, refuses
  before sending

#### Scenario: A buyer completes a purchase

- **WHEN** a purchase settles and a key is issued
- **THEN** the buyer is shown the key, the base URL, and the model name needed
  for a first request
