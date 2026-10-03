## ADDED Requirements

### Requirement: Local inference stack composition

The development stack MUST be able to stand up the inference market beside the
compute and API-credits markets: a registry instance selecting the `inference`
filter specification with its own authority identity, the inference authority,
the gateway in front of a model server, and the inference storefront. Each
signing role MUST have its own development credential supplied through an
explicit, role-scoped reference, and no credential value may be committed in a
stack definition. The stack MUST run without a GPU and without fetching a model
from an external host.

#### Scenario: The full stack is brought up

- **WHEN** a contributor brings up the root development stack with the
  development identities
- **THEN** three registry instances serve three schema identities, and the
  inference authority, gateway, model server, and storefront report healthy

#### Scenario: The inference stack is brought up alone

- **WHEN** a contributor brings up the inference wrapper
- **THEN** the development chain and the inference services start with no VM or
  API-credits service

#### Scenario: A development credential is missing

- **WHEN** a required inference credential reference is unset
- **THEN** the stack refuses to start naming the missing reference

#### Scenario: A real model server is wanted locally

- **WHEN** a contributor selects the stack's model-server profile
- **THEN** the gateway fronts that model server and no other service's
  configuration changes
