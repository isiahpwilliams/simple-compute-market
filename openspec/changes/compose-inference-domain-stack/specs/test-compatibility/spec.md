## ADDED Requirements

### Requirement: Inference end-to-end deal path

The inference domain MUST have an end-to-end scenario, built on the shared
domain-neutral helpers, that proves one complete deal against running services:
discovery by model on the inference registry, negotiation of a new key,
settlement on the development chain, delivery of a key and a materialization
carrying the listing's rate card, a successful model request, refusal of an
unlisted model without charge, exhaustion, a top-up of the existing key, and a
streamed response. The scenario MUST run against a deterministic model server so
its assertions are exact.

#### Scenario: The lane runs

- **WHEN** the inference end-to-end lane runs, building the inference images
  and every registry its scenarios read
- **THEN** the inference deal scenario runs in it and observes each stage in
  order through the public buyer and seller boundaries

#### Scenario: The buyer's schema filter is exercised

- **WHEN** the scenario discovers inference listings with compute and
  API-credits registries also configured
- **THEN** only the inference registry is queried

#### Scenario: A lane setting is missing

- **WHEN** the lane's configuration lacks a value the inference scenario reads
- **THEN** the scenario fails naming the setting rather than skipping
