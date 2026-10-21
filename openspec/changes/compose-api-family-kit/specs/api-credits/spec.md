## ADDED Requirements

### Requirement: API credits composes the api family kit

The API-credits domain MUST compose the `api` family's vocabulary and kit for
every concern the kit owns — the purchase shape, issuance models and digests,
issuance evidence, the authority's key service and ledger, the storefront's
issuance and settlement composition, the negotiation adapters, the quota listing
binding and publication, the buyer flows, the mechanism stages, and the bearer
gate — and MUST retain no domain-local implementation of any of them. Its wire
shapes, digests, database rows, migration identifiers, environment prefixes, and
observable behaviour MUST be unchanged by that composition.

#### Scenario: A grant issued before the kit is read after it

- **WHEN** the family authority, deployed with the `api-credits` label, reads a
  grant and its request digest written by the pre-kit service
- **THEN** it recomputes the same fulfillment identity and digest and accepts an
  exact retry without a second grant

#### Scenario: A domain-local copy is sought

- **WHEN** the API-credits packages are searched for an issuance client, a
  digest function, a key service, a settlement stage, or a gate of their own
- **THEN** none is found; each is imported from a `domains/api` distribution
