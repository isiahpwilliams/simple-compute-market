## ADDED Requirements

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

### Requirement: Buyer plugin discovers under the inference schema identity

The inference buyer plugin MUST declare the `inference` schema identity, MUST
query only registries declaring it, and MUST resolve the rate-bound
co-requirement from the served filter specification rather than from code,
refusing an unpaired bound before sending it.

#### Scenario: Compute and API-credit registries are also configured

- **WHEN** the buyer's configuration names a compute registry, an API-credits
  registry, and an inference registry
- **THEN** inference discovery queries only the registry declaring the
  `inference` schema identity

#### Scenario: Buyer bounds a rate without naming an asset

- **WHEN** a buyer asks the plugin for a rate bound and no `rate_card_asset`
- **THEN** the plugin, compiling against the served specification, refuses
  before sending

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

### Requirement: A grant records the accepted listing's rate card

Issuance MUST record on the credit grant the rate card of the listing the buyer
accepted, read from the accepted listing artifact rather than from the listing
as currently published.

#### Scenario: Seller republishes between acceptance and issuance

- **WHEN** a seller republishes a model's listing with a new rate card after a
  buyer accepted the previous one and before the grant is issued
- **THEN** the issued grant records the card the buyer accepted
