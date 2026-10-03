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
mechanism, `alkahest.v1`, and MUST NOT depend on a hosted-settlement
distribution. A configuration naming any other mechanism MUST be refused at
startup rather than ignored.

#### Scenario: Another mechanism is configured

- **WHEN** a storefront configuration's settlement priority names a mechanism
  other than `alkahest.v1`
- **THEN** startup fails naming that mechanism before any request is served

#### Scenario: Role wheels are inspected

- **WHEN** the inference role wheels' requirements are read
- **THEN** none requires a hosted-settlement distribution

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

The buyer plugin MUST offer discovery filters for model, model family,
quantization, modality, supported parameter, provenance, minimum context length,
and the rate bounds, compiled from the registry's served filter specification.
A completed purchase MUST give the buyer the key, the gateway base URL, and the
served model name.

#### Scenario: A buyer searches by model

- **WHEN** a buyer lists inference offers for a `model_id`
- **THEN** only registries declaring the `inference` schema are queried and only
  listings for that model are returned

#### Scenario: A buyer completes a purchase

- **WHEN** a purchase settles and a key is issued
- **THEN** the buyer is shown the key, the base URL, and the model name needed
  for a first request
