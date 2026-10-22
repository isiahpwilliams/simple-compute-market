## ADDED Requirements

### Requirement: Admission authority is synchronous and singular

The inference authority that holds keys, grants, pinned rate cards, and
balances MUST be the only component consulted on whether a request may proceed.
An external rating, metering, or billing system MAY receive usage records as a
downstream feed and MUST NOT be consulted on the admission path or hold a
balance the authority treats as authoritative.

#### Scenario: Downstream rating system is unavailable

- **WHEN** a configured downstream usage consumer cannot be reached
- **THEN** admission decisions continue from the authority's own balance and the
  undelivered records are retained for later delivery rather than blocking
  requests
