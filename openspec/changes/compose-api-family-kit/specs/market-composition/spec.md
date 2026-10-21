## ADDED Requirements

### Requirement: The api family shares one access vocabulary and kit

The API-selling domains — API credits and inference — MUST form the `api`
family, with one vocabulary package under `domains/api` and one family kit of
distributions beneath it, placed under the family directory the scope rule
names. Neither domain MUST define the purchase shape, issuance digests, key
authority, issuance composition, buyer flows, mechanism stages, or bearer gate
of its own, and neither MUST obtain them by importing the other. A third
API-selling domain MUST be able to compose the kit by supplying contributions
alone, without the kit learning its listing schema or branching on its identity.

#### Scenario: Both domains compose the kit

- **WHEN** the API-credits and inference storefronts, authorities, gates, and
  buyer plugins are built
- **THEN** each imports the family distributions and no sibling domain, and the
  architecture check classifies every family project from its path with no
  override row

#### Scenario: A third API-selling domain is added

- **WHEN** a new domain under the `api` family supplies its contribution bundle
- **THEN** it composes the storefront, authority, gate, and buyer flows without
  a change to any `domains/api` distribution
