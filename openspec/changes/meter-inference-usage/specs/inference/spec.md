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

### Requirement: Each usage record is debited once

A grant's grant identity and a request identity together name one usage record,
and the authority MUST debit each such pair at most once, whatever number of
times its evidence is presented.

#### Scenario: Evidence for one request is presented twice

- **WHEN** valid usage evidence for one request on a grant is presented a second
  time
- **THEN** the grant's balance is debited once

### Requirement: Consumption is priced by the grant's recorded card

Consumption against a credit grant MUST be priced by the rate card the grant
recorded at issuance. A republished listing with a different rate card MUST
affect only grants issued after republication.

#### Scenario: Seller reprices after a sale

- **WHEN** a seller republishes a model's listing with higher rates after a buyer
  has purchased a balance under the previous card
- **THEN** the buyer's existing grant consumes at the previous card and only new
  purchases consume at the new one
