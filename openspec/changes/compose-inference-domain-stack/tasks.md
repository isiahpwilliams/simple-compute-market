# Implementation Tasks

Implementation is gated: it starts only once `add-inference-domain-contract`
(the `inference.v1` vocabulary this change composes), `compose-api-family-kit`
(the `api` family kit; its index row advances at archive cleanup), and
`repair-storefront-alkahest-configuration` (the development stack's Alkahest
readiness, which the deal scenario needs green) are each `archived` in
`openspec/changes/README.md`. Sections 1–4 change the family and touch no
inference role; sections 5–8 are the four inference roles, configuration over
the kit; sections 9–11 are the stack and its lane; section 12 closes out.
Sections are ordered by real dependency.

Every task names the decision in `design.md` (`D<n>`, or a review-labelled
decision as `review 0N F<m>`), the delta requirement, or the repository
obligation it answers to, and the evidence that proves it. A task whose inputs
turn out not to reach what its decision names stops and records the gap in
`design.md` rather than deciding; `design.md`'s open questions — the first
attestation `kind`, the hosting domain, charge idempotency on retries, and the
first seller, paying buyer, and settlement option — are decided nowhere in this
file.

Names this plan introduces for fields, modules, environment variables, and
statuses are implementation naming on the precedent's pattern, not design; the
decisions fix the behaviour, and an implementer who finds a name clashes with
an existing one keeps the behaviour and records the rename in the section's
note.

## 1. Family vocabulary: accepted terms on the issuance subject

Delivers the optional accepted terms, terms digest, and request charge on the
family's issuance subject, request digest, and signed evidence, omitted when
unset so API credits' bytes are unchanged, and the delivery context the
selling library hands the public-result extension (review 02 F1; review 03 F3
as amended by review 04 F1 and F2; D3; api-family delta "The issuance subject
may carry accepted terms" and "The public-result extension receives the
delivery's settlement context"; the deltas' "API credits issues without terms"
and "API credits delivers without an extension" scenarios).

- [x] 1.1 Confirm by inspection, before writing anything, that the design's
      "What exists" still holds on the target branch: `IssuanceSubject`
      (`domains/api/selling/src/arkhai_api_selling/contributions.py`) has
      `service`, `resource_id`, `endpoint` only; `_request_digest` in
      `domains/api/src/arkhai_api/issuance.py` digests exactly the eight keys it
      lists; `IssuanceEvidenceBodyV1` in `domains/api/src/arkhai_api/evidence.py`
      carries no terms field; `VerifyResponse` in
      `domains/api/contracts/src/arkhai_api_contracts/models.py` is `valid`,
      `status`, `balance`; and `domains/apicredits/tests/fixtures/pins/issuance_pins.json`
      holds only API-credits cases. Record drift in `design.md` rather than
      working around it (`AGENTS.md`, "Discuss").
      *Note:* confirmed on the branch at 9f21a6c9e: the subject, the eight-key
      digest, the evidence body, `VerifyResponse`, and the API-credits-only pins were
      as described. Drift found later: `IssuanceRequest` is also a component of the
      API-credits service's recorded OpenAPI baseline (re-recorded in 1.8).
- [x] 1.2 `domains/api/src/arkhai_api/issuance.py`: `IssuanceRequest` gains
      optional `accepted_terms` (a JSON object, canonical on the wire),
      `terms_digest` (`DIGEST_PATTERN`), and `request_charge` (`ge=1`,
      `le=2**53 - 1`, the canonical JSON integer domain; plan review 06 F3 as
      amended by 07 F1), each
      `None` by default and excluded from serialisation when unset; a validator
      requires the three together and the digest to equal `sha256:` of the
      canonical JSON of `accepted_terms`. `_request_digest` and
      `issuance_request_digest` add `terms_digest` and `request_charge` to the
      digested payload only when set, so an API-credits request digests the
      same eight keys as today (review 03 F3 "Wire bytes": the digest carries
      the digest, not the payload). `issuance_request(...)` takes the three as
      keyword arguments.
      *Note:* `accepted_terms_digest`, `MAX_REQUEST_CHARGE`, and the
      `RequestCharge` type are exported beside the request. Omission is a wrap
      `model_serializer` (`omit_unset`) rather than pydantic's `exclude_if`, which
      needs pydantic 2.11 while the package declares `pydantic>=2`; the serializer
      carries no return annotation, which would replace the model's published
      serialisation schema. `issuance_request` validates the charge against the
      same `RequestCharge` bound before computing a digest, so `2**53` is refused
      as a validation error rather than by canonical JSON; a wire request with `0`
      or `2**53` is refused by the label-bound model.
- [x] 1.3 `domains/api/src/arkhai_api/evidence.py`: `IssuanceEvidenceBodyV1`
      and `ExpectedIssuanceEvidenceV1` gain optional `terms_digest` and
      `request_charge`, omitted when unset, so `_signing_bytes` and
      `issuance_evidence_digest` are unchanged for a body without them;
      `verify_issuance_evidence` binds them to the expected values when the
      expectation carries them (review 03 F3; api-family delta "the digest and
      charge MUST enter ... the signed evidence").
      *Note:* the body requires `terms_digest` and `request_charge` together;
      verification binds each only when the expectation carries it, and the
      request digest already binds both. `IssuanceEvidenceService`'s self-consistency
      check now carries them into its expectation.
- [x] 1.4 `domains/api/selling/src/arkhai_api_selling/contributions.py`:
      `IssuanceSubject` gains optional `accepted_terms`, `terms_digest`, and
      `request_charge`, documented as what the domain's projection reads from
      the accepted listing. `domains/api/selling/src/arkhai_api_selling/issuance.py`:
      `prepare_issuance_request` copies the three from the subject onto the
      request, and the evidence body the storefront signs carries the digest
      and charge when the subject has them (review 02 F1, as amended by review
      04 F1 and F2). `connection_payload` is unchanged: the terms are not
      delivery metadata.
      *Note:* the body the storefront signs is built in the Alkahest selling
      stage (`selling-alkahest/.../stage.py`), not in `issuance.py`. `fulfill` now
      returns the issued request beside the result (`issuance_request`), and the
      stage spreads `evidence_terms(request)` into the body, so the signed terms are
      the ones the answered request digest covers. No other stage signs evidence.
- [x] 1.5 `domains/api/selling/src/arkhai_api_selling/contributions.py`: a
      frozen `DeliveryContext(mechanism: str, settlement_ref: str | None)`,
      and `PublicResultExtension` becomes
      `Callable[[Mapping[str, Any], IssuanceResult, DeliveryContext], Mapping[str, Any]]`.
      `domains/api/selling/src/arkhai_api_selling/issuance.py`: `fulfill`
      passes `DeliveryContext(evidence.mechanism, evidence.settlement_ref)`
      as the extension's third argument; nothing else in the delivery moves
      (D3 "The third input is new to the kit"; api-family delta "The
      public-result extension receives the delivery's settlement context").
      The selling library's `bundles.py` `with_extension` helper and the
      existing extension test take the third parameter.
      *Note:* `bundles.py`'s `with_extension` only replaces the bundle's
      extension, so the change there is its docstring; the existing extension tests'
      lambdas take the third parameter. `with_terms` was added beside it.
- [x] 1.6 Unit tests, vocabulary (`domains/api/tests/unit/test_issuance_pins.py`,
      `test_evidence.py`): a request without terms digests and signs to the
      same bytes as before the fields existed; a request with terms digests
      the digest and charge and not the payload; a digest that does not match
      the payload is refused; a `request_charge` of `2**53 - 1` is accepted
      and `2**53` refused by the request model before any digest is computed
      (plan review 07 F4); evidence verification binds the digest and
      charge. Unit tests, selling (`domains/api/selling/tests/unit/test_issuance.py`):
      the subject's three values reach the request and evidence, and a subject
      without them produces today's request; an extension receives the
      evidence's mechanism and reference beside the listing and result, and a
      bundle without an extension saves the same public-result keys as before
      (api-family delta scenarios "A domain builds its materialization in the
      extension", "API credits delivers without an extension").
      *Note:* vocabulary unit level — `test_issuance_pins.py` (unset terms
      serialise nothing; the digest covers the terms digest and charge, not the
      payload; mismatch and partial sets refused; `2**53 - 1` accepted, `0` and
      `2**53` refused through `issuance_request` and on the wire) and
      `test_evidence.py` (an unpinned body carries no terms keys — byte equality
      with the recorded pins is `test_every_pin_matches_byte_for_byte_under_api_credits`;
      set terms are signed and paired; verification binds them). Selling unit
      level — `test_issuance.py` (subject terms reach the request and its
      `evidence_terms`; an unpinned subject produces an unpinned request; an
      extension receives the mechanism and a `settlement_ref` distinct from the
      negotiation id). Selling-Alkahest library integration —
      `test_delivery.py` (a delivery under a pinning bundle publishes evidence
      whose body carries the terms digest and charge beside the answered request
      digest, and an unpinned one publishes none) against real storefront
      persistence and the settlement journal.
- [x] 1.7 `domains/apicredits/tests/fixtures/pins/issuance_pins.json` and
      `domains/apicredits/tests/test_issuance_pins.py`: the recorded API-credits
      cases are unchanged byte for byte, and the fixture gains one inference
      case under `IssuanceLabel("inference")` with the three fields present,
      pinning its request digest, signed evidence, and result bytes (review 03
      F3 "Wire bytes"; api-family delta scenario "API credits issues without
      terms"; inference delta scenario "The same request is digested on both
      sides", whose two-label difference the case records against the
      equivalent API-credits case). The fixture's generator (`main`) writes the
      new case; the test refuses an input set the fixture does not record.
      *Note:* the API-credits cases stay under `cases`, byte for byte; the
      inference case is under a separate `inference_cases` key and pins the fulfillment
      identity, request digest, canonical issuance request, evidence digest, signed
      evidence, portable reference, and the API-credits request digest of the same
      inputs. The generator now adds an absent case set and still never rewrites a
      recorded one; the fixture diff is additions only.
- [x] 1.8 **Verification.** `make test-api` (the vocabulary's unit level and its
      `tests/integration/test_distribution.py`, and the selling library's unit
      and library-integration levels); `make test-apicredits` (the domain's
      unit-level pins and distribution tests). `make test`. No dependency or
      lock changes, so `make check-packaging` is not owed here. Once deployed,
      `e2e_credits_deal` exercises the unchanged API-credits path and
      `e2e_inference_deal` (section 11) the fields present; none is owed
      beyond those.
      *Note:* `make test-api` passed (the vocabulary 78, contracts 43, client 25,
      authority 69, selling 214, selling-Alkahest 34, and the other family
      suites); `make test-apicredits` passed (domain pins and distribution, the
      service with its compatibility baselines, storefront, buyer, sample app,
      and the TypeScript and Rust middleware conformance). `make -k test`: every
      target passed but two. `test-storefront` failed only in
      `tests/integration/test_alkahest.py`, which needs `anvil` on `PATH`, and
      passed in full (1103 and 448) once `$HOME/.foundry/bin` was on it.
      `test-provisioning` fails one unit test,
      `test_provisioning_bootstrap_dotenv_uses_environment_layer_without_dotenv_local`,
      only when run in the suite (it passes alone and with its module); the
      provisioning service installs no api-family distribution, so this section
      cannot reach it, and it is left as found. `make check-change` passed.
      **Baseline re-record:** the three optional `IssuanceRequest` properties
      (`accepted_terms`, `terms_digest`, `request_charge`, each nullable) are
      new in the API-credits service's served OpenAPI, so
      `domains/apicredits/service/tests/fixtures/baseline/openapi.json` was
      re-recorded once, in place, from the running service; its diff is those
      three properties alone, and every other baseline record is unchanged (the
      owner's decision, `interventions.jsonl`). The compliance check's findings
      were fixed — the serializers carry no return annotation, the evidence's
      terms come from the issued request rather than a second projection, the
      context test distinguishes `settlement_ref` from the negotiation id, the
      signed body's terms are tested through a delivery, history-worded
      comments and test names were restated — except one declined: `omit_unset`
      stays a public helper of `arkhai_api.issuance`, since `evidence` in the
      same package imports it.
      **Versions, against the plan:** the plan owed no version change, but the
      Alkahest stage now reads `fulfill`'s new `issuance_request` key and the
      vocabulary's new fields cross distributions, so `arkhai-api` 0.2.0,
      `arkhai-api-selling` 0.5.0 (requiring `arkhai-api>=0.2.0`), and
      `arkhai-api-selling-alkahest` 0.2.0 (requiring the new selling), with the
      API-credits storefront's floors raised; `make lock` relocked the 17
      projects that record them (version lines only) and `make check-packaging`
      passed; the focused suites of every relocked project passed after it.
      *Handoff:* section 2 re-records the same baseline for its verify and
      consume fields. A wrap `model_serializer` with a return annotation silently
      replaces the model's serialisation schema; keep new ones unannotated.
      `sed -i ''` fails in this shell (GNU sed); the Alkahest library tests need
      `$HOME/.foundry/bin` on `PATH`.

## 2. Family contracts and authority: pinned terms and key scope

Delivers the optional scope on `verify` and `consume`, the pinned terms
`verify` returns, the `grant_terms` table, and the authority's scope rule and
refusals (review 01 F4; review 03 F1; review 03 F3 as amended by review 04 F1
and F2; api-family delta "The issuance subject may carry accepted terms" and
"A key is scoped to its first grant").

- [x] 2.1 `domains/api/contracts/src/arkhai_api_contracts/models.py`:
      `VerifyRequest` and `ConsumeRequest` gain optional `service` and
      `resource_id`; `VerifyResponse` gains optional `accepted_terms`,
      `terms_digest`, and `request_charge`, serialised only when set (the
      model's `extra="forbid"` stays, so an authority that sets none answers
      today's three keys). `IssuanceResponse` is unchanged: the storefront
      holds the three values it sent, and `verify` is where they are read
      back, so the strict `IssuanceResult` the canonical client parses stays
      as it is (plan review 06 F2). The route declarations in
      `declarations.py` are unchanged: no new route (api-family delta "when
      absent ... byte-identical"; review 03 F1 "The fields are optional on
      both requests").
      *Note:* the scope fields and the response's terms are omitted when unset
      through the same unannotated wrap serializer section 1 uses. `VerifyResponse`
      is not a component of the served OpenAPI (the verify route returns a mapping),
      so only `VerifyRequest` and `ConsumeRequest` changed the baseline (2.8).
      `ConsumeBatchItem` carries no scope: the batch path is unscoped. The
      contracts' `CONSUME_REFUSALS` gains `key_out_of_scope`; the refusal baseline
      records only what an unscoped caller can receive, and `test_refusals.py`
      says so.
- [x] 2.2 `domains/api/authority/src/arkhai_api_authority/models.py`: a
      `GrantTerms` model on table `grant_terms` — `grant_id` (foreign key to
      `credit_grants.id`, primary key), `accepted_terms` (canonical JSON text),
      `terms_digest`, `request_charge` — and `CreditGrant` untouched, so
      `_validate_grant_schema`'s exact column set still passes against a
      migrated database (review 03 F3 "A separate table"). No key column: a
      key's pinned values are its first grant's row.
      *Note:* `grant_terms.request_charge` is an integer column; the charge's
      `2**53 - 1` bound is the request model's, checked before anything is written.
- [x] 2.3 `domains/api/authority/src/arkhai_api_authority/migrations.py`: one
      new `Migration` at the end of `_MIGRATIONS`, in the chain's identifier
      pattern, creating `grant_terms` when absent; `_validate_grant_schema` and
      every earlier step unchanged (review 03 F3 "Validation ordering"; D15 —
      the inference database runs this chain from its first step).
      *Note:* step `20261030_006_grant_terms` creates the table in explicit DDL,
      as the chain's other steps write theirs, so it does not follow later edits
      to the model; `run_migrations`' `create_all` creates the table first on a
      fresh or upgraded database, and the step creates it where the chain runs
      alone (`apply_schema_migrations`), which the migration test exercises.
- [x] 2.4 `domains/api/authority/src/arkhai_api_authority/keys_service.py`:
      `issue` takes `accepted_terms`, `terms_digest`, `request_charge`,
      verifies the digest against the canonical payload before writing (a
      mismatch is an `IssuanceError`), records a `GrantTerms` row with the
      grant in the same transaction, and returns today's result unchanged:
      the three are persisted, never returned from `issue`, and read back
      only through `verify` (plan review 07 F2). A
      new-key grant pins the key; an existing-key issuance compares the
      request's `(service, resource_id, terms_digest)` against the key's first
      grant and its row (an unpinned first grant admits only unpinned top-ups)
      and refuses a difference with the named reason `key_out_of_scope`,
      recording no grant and leaving the balance unchanged (review 01 F4;
      review 02 F1; api-family delta scenario "A key is topped up from another
      listing"). The replay check (`_assert_replay`) treats the three as part
      of the immutable request.
      *Note:* a digest mismatch is `IssuanceError("terms_digest_mismatch")`, raised
      before the request model or any query, answered `422` by the route service;
      `key_out_of_scope` on issuance is `409`. The scope check runs after the
      existence, revocation, and ownership checks and before quota is touched, and
      its refusal names the first grant's service and resource. It compares the
      terms digest *and* the request charge, stricter than the task's
      `(service, resource_id, terms_digest)`, so one balance never carries two
      charges. The terms row is flushed and added inside the same `try` as the
      commit, so by construction a duplicate fulfillment still reaches the replay
      path; no test reaches that handler with terms, since the service's mutation
      lock serialises in-process issuance.
- [x] 2.5 `keys_service.py`: `verify` returns the key's pinned
      `accepted_terms`, `terms_digest`, and `request_charge` from its first
      grant's row, omitted for an unpinned key; `verify` and `consume` take
      optional `service` and `resource_id` and, when either is present, refuse
      a key whose first grant's scope differs with `valid=False,
      status="key_out_of_scope"` (verify) or `ok=False,
      reason="key_out_of_scope"` (consume), before any balance change; absent,
      both behave as today (review 03 F1; api-family delta scenario "A key is
      presented at another offering's gateway"). A read of a grant's full
      accepted terms, verified against its digest, is available through
      `list_grants`, for the later consumer the delta's "Metering reads the
      accepted card" scenario names.
      *Note:* a scoped `verify` checks the secret first, so a wrong secret answers
      as it always did; an out-of-scope key answers `valid=False`,
      `status="key_out_of_scope"`, `balance=0`, revealing neither balance nor terms. A
      scope names `service`, `resource_id`, or both, and only the named ones are
      compared. A key with no issuance grant matches no named scope; an unscoped
      `consume` does not query the grant. `list_grants` carries each pinned grant's
      terms, read in one query and re-verified against their digest. A terms row
      that no longer matches its digest fails the read (an internal error), since
      it is a corrupt store rather than a refusal.
- [x] 2.6 `domains/api/authority/src/arkhai_api_authority/route_services.py`:
      `AuthorityRouteService.issue` accepts the three request fields and
      returns the unchanged response, `verify` and `consume` carry the new
      fields; `_ISSUANCE_STATUS` and `_CONSUME_STATUS` map `key_out_of_scope`
      to a refusal status. `domains/apicredits/service/src/apicredits_service/controllers/keys_controller.py`
      forwards the request models' optional fields to the route service, so
      the API-credits authority honours scope when a caller sends it and is
      byte-identical when none does (api-family delta "when present, the
      authority MUST refuse"; its "The API-credits pins are replayed"
      requirement holds, proven in section 1).
      *Note:* `consume`'s `key_out_of_scope` is `403`. The API-credits
      controller forwards the optional fields; forwarding is proven through the
      typed clients in 2.8.
- [x] 2.7 Library-integration tests
      (`domains/api/authority/tests/integration/test_keys_service.py`): a
      pinned issuance stores the three values and its result carries none of
      them, so the strict issuance response still parses; a digest mismatch is
      refused; an existing-key top-up under another `(service, resource_id)` or
      another digest is refused with `key_out_of_scope`, no grant recorded,
      balance unchanged; an unpinned key accepts only unpinned top-ups; `verify`
      and `consume` with a differing scope refuse uncharged and with no scope
      behave as before; `verify` returns pinned terms. Migration tests
      (`test_migrations.py`): a database at the previous chain head migrates,
      creates `grant_terms`, reads existing grants as unpinned, and still
      passes `_validate_grant_schema`; the previous chain's validation against
      the migrated schema is the in-process half of the delta's "The authority
      is upgraded and rolled back" scenario (review 04 F1: no down-migration).
      *Note:* library integration (`test_keys_service.py`, real SQLite and the
      real site ledger): pinned issuance stores and lists the terms with an
      unchanged result; verify returns them, and nothing for an unpinned key; a
      mismatched digest refuses with quota untouched; a top-up under another service,
      resource, terms, or none refuses `key_out_of_scope` with no grant, balance
      unchanged, quota untouched; an in-scope top-up grants; an unpinned key admits
      only unpinned top-ups; a replay under other terms conflicts; verify and consume
      out of scope refuse uncharged with no usage event, and in scope or unscoped
      admit and charge. `test_migrations.py`: a database built at the previous chain
      head, holding a grant, gains `grant_terms` from the step itself, with no row
      for the grant, and passes `check_schema_version` under the new chain and
      under the previous chain's list — the previous image's code is not run here;
      its grant-schema check is the same unchanged function, and the live half is
      `e2e_credits_service_rollback`. The previous chain is substituted by patching
      the module's `_MIGRATIONS`, as the file's existing failed-migration test does.
      Unit (`test_route_services.py`): the new reasons' statuses.
- [x] 2.8 Application-integration tests through the typed client
      (`domains/apicredits/service/tests/integration/test_credits_signed_roundtrip.py`
      and `test_compat_baseline.py`): an API-credits issuance, verify, and
      consume without the fields match the recorded baseline bodies; a verify
      with a scope the key's grant matches admits and with one it does not
      refuses `key_out_of_scope` without consuming (api-family delta "A key is
      scoped to its first grant").
      *Note:* application integration through the typed clients, against the
      real credits service over ASGI with real signing
      (`tests/integration/test_pinned_terms_and_scope.py`): a pinned issuance
      through `AuthorityClient` verifies through `TokensClient` with its terms,
      digest, and charge; a top-up under other terms is refused `key_out_of_scope`
      with the balance unchanged; a key verified or consumed under another service
      or resource is refused uncharged, and in scope or unscoped admits and charges.
      The unscoped bodies are the compatibility baseline's recorded ones
      (`test_compat_baseline.py`, unchanged refusals and routes). The scoped calls
      needed `TokensClient`'s scope parameters, so task 3.1 was done here (see its
      note). **Baseline re-records:** the served OpenAPI gained the optional `service`
      and `resource_id` on `VerifyRequest` and `ConsumeRequest`, and the schema
      baseline (`schema.json`) gained the `grant_terms` table and migration
      `20261030_006_grant_terms`; both were re-recorded once, in place, from the
      running service, each diff additions only, on the owner's section 1 decision
      for additive changes.
- [x] 2.9 **Verification.** `make test-api-authority` (library integration),
      `make test-api` (the contracts' unit level), `make test-apicredits`
      (the service's application integration through `AuthorityClient` and
      the gate's `TokensClient`, and its compatibility baselines). `make test`.
      `domains/api/contracts` and `domains/api/authority` versions bump for the
      wire and schema additions, so `make lock PROJECTS="domains/api/contracts
      domains/api/authority domains/apicredits/service domains/api/gate
      domains/api/client domains/api/selling"` and `make check-packaging`.
      Once deployed, `e2e_credits_service_rollback` is the live half of the
      upgrade-and-rollback scenario: the previous image
      (`arkhai:apicredits-service-prekit`) starts against a database the new
      image migrated, because `credit_grants` is unchanged; record its run at
      closeout. `e2e_inference_deal` exercises the pinned charge and the scope
      refusal.
      *Note:* versions: `arkhai-api-contracts` 0.5.0, `arkhai-api-authority`
      0.2.0, `arkhai-api-gate` 0.2.0 (3.1's client), `arkhai-apicredits-service`
      0.9.0, with floors raised where the new fields are imported; `make lock`
      relocked every project recording them. `make test-api` passed (contracts 47,
      authority 88, gate 27 with the parity suite, and the rest); `make
      test-apicredits` passed after the schema re-record (service integration 40);
      `make check-packaging` passed. `make -k test`: every target passed but the
      provisioning unit test that fails only in its suite (section 1's note), and
      `scripts/tests/test_validate_slice.py`'s 0.2-second credential-helper case,
      which timed out under the full run's load and passed in `make
      test-release-tooling` alone (1136 passed). The rollback scenario and the
      inference deal are owed once deployed, as planned.
      *Handoff:* the gate's parity test now holds a sent body between the model's
      required and declared fields, since an unscoped body omits the optional scope;
      `ConsumeBatchItem` and the gate's batch flush carry no scope, so section 3's
      scoped charge must not batch, or must consume singly.

## 3. Family gate: a separable verify step and the key's charge

Delivers the gate's verify step beside `authorize`, the verified charge, and
the scope the gate sends, with the conformance trace unchanged (review 01 F3;
review 03 F1; api-family delta "The gate verifies and charges in separable
steps"; D16's ordering, verification before charge).

- [x] 3.1 `domains/api/gate/src/arkhai_api_gate/client.py`: `VerifyResult`
      gains optional `accepted_terms`, `terms_digest`, and `request_charge`
      read from the response when present; `TokensClient.verify` and
      `consume` take optional `service` and `resource_id` and send them only
      when set, so an unscoped client's request bodies are byte-identical
      (review 03 F1). The parity test (`tests/test_contract_parity.py`) keeps
      the local spelling equal to `contracts`' declarations.
      *Note:* done in section 2's commit, because relocking the gate onto
      contracts 0.5.0 broke its parity test against the new `VerifyResponse` fields
      and the plan's 2.8 needed scoped calls through `TokensClient`. `VerifyResult`
      gains the three terms fields; `verify` and `consume` take optional `service` and
      `resource_id`, sent only when set. The parity test now requires an unscoped
      body to hold every required field and no unset optional one, and a scoped
      client to send its scope and parse a pinned key's terms;
      `KEY_OUT_OF_SCOPE` joins the declared consume refusals.
- [x] 3.2 `domains/api/gate/src/arkhai_api_gate/config.py`: `GateConfig`
      gains optional `scope_service` and `scope_resource_id`, read by
      `from_env` as `SCOPE_SERVICE` and `SCOPE_RESOURCE_ID` under the
      deployment's prefix, unset by default (the sample app and every
      API-credits deployment set neither).
      *Note:* unit (`tests/test_config.py`): both unset by default, read under
      the prefix when set.
- [x] 3.3 `domains/api/gate/src/arkhai_api_gate/gate.py`: `TokenGate.verify(authorization)`
      returns either a deny `GateDecision` (401 missing or invalid, 403
      revoked, 403 `key_out_of_scope` when the authority refuses by scope) or
      a verified key value carrying `key_id`, the cached `VerifyResult`'s
      terms, digest, and charge; `TokenGate.charge(verified, idempotency_key=None)`
      charges `verified.request_charge` when verification returned one, else
      `amount_per_request`, through today's `_charge` path (batching,
      low-balance synchrony, exhaustion memory, 402 with the purchase pointer);
      `authorize` becomes `verify` then `charge`, producing the same authority
      exchanges and cached state as before (api-family delta scenario "A check
      between verification and charge refuses"; review 01 F1 "falling back to
      the offering's default only when verification returns none"; D4: no
      idempotency key is introduced). The cached `_KeyState` holds the verified
      terms for the verify TTL (review 01 F2: the gate is otherwise unchanged).
      *Note:* `TokenGate.verify` returns a `GateDecision` denial or a
      `VerifiedKey` (exported); `charge(verified, idempotency_key=None)` falls back
      to the configured amount only when verification returned no charge, and
      answers a key it never verified as invalid (`401`). Charges keep today's
      path, batching included, for scoped and unscoped gates alike: a batch item
      carries no scope, and need not, since a key's scope is fixed by its first
      grant and was checked at verification. (This corrects section 2's handoff,
      which proposed that a scoped gate not batch.) The flush's requeue of an
      unavailable batch keeps each item's own amount rather than the configured
      one, the same value whenever no charge is pinned. A consume refused
      `key_out_of_scope` is answered `403` like the verify refusal.
- [x] 3.4 `domains/api/gate/src/arkhai_api_gate/asgi.py`: `TokenGateMiddleware`
      keeps calling `authorize`; its behaviour is unchanged.
      *Note:* `asgi.py` is untouched.
- [x] 3.5 Unit tests (`domains/api/gate/tests/test_gate.py`): verify then
      refuse leaves the balance unchanged and the fake authority saw only the
      verification; verify then charge equals `authorize` call for call; a
      verified `request_charge` is the amount consumed and its absence falls
      back to the configured amount; a scoped configuration sends `service`
      and `resource_id` on verify and consume and an unscoped one sends
      neither; an authority `key_out_of_scope` status is answered `403`
      uncharged. `tests/test_conformance.py` replays
      `domains/apicredits/middleware/conformance/session.json` unchanged, and
      the TypeScript and Rust gates and the trace are not edited (api-family
      delta "with the same authority exchanges and cached state"; the
      `api-family` capability's "The conformance trace is replayed" scenario).
      *Note:* unit (`tests/test_gate.py`, a scripted client recording each call):
      verify alone calls only verify and returns the pinned terms; the pinned charge is consumed and the configured amount otherwise; a scoped
      configuration sends its scope on verify and consume and an unscoped one sends
      none; a pinned charge is batched and requeued at its own amount; charging a
      key never verified is `401`; verify then charge equals `authorize` in
      decisions, calls, and cache use, synchronous and batched; an out-of-scope
      verify is `403` uncharged and an out-of-scope consume is `403`. `tests/test_conformance.py`
      replays `session.json` unchanged; the trace and the TypeScript and Rust gates
      are not edited. The scoped exchanges against the real authority are
      section 2's application-integration test.
- [x] 3.6 **Verification.** `make test-api-gate` (unit, the conformance
      replay, and the contract parity); `make test-apicredits` for the sample
      app's unit tests (`domains/apicredits/sample-app/tests/test_sample_app.py`),
      which must pass unchanged. `make test`. `domains/api/gate` bumps for the
      new public methods: `make lock PROJECTS="domains/api/gate
      domains/apicredits/sample-app domains/apicredits/service"` and `make
      check-packaging`. Once deployed, `e2e_credits_deal` exercises the
      unchanged `authorize` path through the sample app and
      `e2e_inference_deal` the separable steps through the gateway.
      *Note:* `make test-api-gate` passed (39, the conformance replay and the
      parity suite included); `make test-apicredits` passed, the sample app's
      unit tests unchanged; `make check-packaging` passed; `make -k test` passed
      every target but the provisioning unit test that fails only in its suite
      (section 1's note). No version bump or relock here: the gate went to 0.2.0
      in section 2, for 3.1's client, and has not been released since, so its new
      public `verify`, `charge`, and `VerifiedKey` ship in that same version and no
      requirement or lock changed. The compliance check's findings were fixed
      except the batching restriction, which was dropped instead of recorded as a
      decision (3.3's note).
      *Handoff:* the family gateway (section 4) calls `gate.verify`, then its
      hook, then `gate.charge`, with the gate's `scope_service` and
      `scope_resource_id` set from the offering; a hook refusal never reaches
      `charge`.

## 4. Family gateway library `arkhai-api-gateway`

Delivers the domain-neutral OpenAI-style reverse proxy as one family library
consuming a `GatewayOffering`, with the per-request verification hook and the
request ordering model check → verify → hook → charge → forward (D2; review 02
F3; review 01 F3; review 02 F2 as amended by review 03 F2 and review 04 F3;
D16; api-family delta "A gateway in front of a model server is one family
library"; inference delta "The buyer's credential stops at the gateway" and
"Streaming responses are forwarded unbuffered").

- [ ] 4.1 Create `domains/api/gateway/` with `pyproject.toml`
      (`arkhai-api-gateway`, hatchling, `packages = ["src/arkhai_api_gateway"]`),
      depending on `arkhai-api-gate[signed]` and `httpx` and on the ASGI
      framework the API-credits sample app already uses (`fastapi`,
      `uvicorn`), a `Makefile` with the one-line `reinit` target
      (`docs/development/BUILD_AND_PACKAGING.md`, "Project environments"), and
      `tests/unit/` and `tests/integration/` roots. The architecture check
      reads `domains/api/gateway` as a family library under `domains/api`
      (`docs/development/ARCHITECTURE.md`, "Package and dependency layers");
      the library declares and imports no domain distribution (api-family delta
      scenario "A domain is imported by the library", which `make
      check-architecture` fails on).
- [ ] 4.2 `domains/api/gateway/src/arkhai_api_gateway/offering.py`:
      `GatewayOffering`, a frozen value of the service name the gateway admits
      in a request's `model`, the key scope it enforces (`service`,
      `resource_id`), the default per-request charge, the gate's
      `PurchasePointer`, the upstream base URL and the path of its credential
      file, and the current canonical terms as verification input (a JSON
      object or `None`); it validates that the service is non-empty and the
      charge non-negative and understands nothing else (review 02 F3).
- [ ] 4.3 `domains/api/gateway/src/arkhai_api_gateway/verification.py`: the
      `VerificationHook` protocol — called with the offering's current
      canonical terms, the key's accepted terms payload, and their digest as
      `verify` returned them, returning a refusal (status and error code) or
      `None` — and `admit_all`, the default (D16; review 02 F2; review 03 F2;
      review 04 F3). No proof `kind` is defined here.
- [ ] 4.4 `domains/api/gateway/src/arkhai_api_gateway/app.py` and `proxy.py`:
      `create_gateway_app(offering, gate, *, verification=admit_all, http=None)`
      serving `POST /v1/chat/completions` and `POST /v1/completions`,
      `GET /v1/models` listing only the offering's service, and `/health`
      ungated. Each gated route reads the JSON body, answers `404` with a
      named error for a `model` other than the offering's before any
      authority call, then `gate.verify` (its deny decisions pass through:
      `401`, `403`, `403 key_out_of_scope`), then the hook with the offering's
      current terms and the verified key's accepted terms and digest (a
      refusal is answered uncharged), then `gate.charge` (`402` with the
      purchase pointer on exhaustion), then forwards to the upstream with the
      buyer's `Authorization` replaced by the deployment's own credential read
      from the offering's credential file, streaming the upstream response as
      it arrives — server-sent events when the body sets `stream` — and never
      buffering it (D2; review 01 F3; D4: no idempotency key is passed;
      inference delta "The gateway admits only paid requests for listed
      models", "The buyer's credential stops at the gateway", "Streaming
      responses are forwarded unbuffered").
- [ ] 4.5 Unit tests (`domains/api/gateway/tests/unit/`): with a fake gate
      and a fake upstream, an unlisted model is `404` and the gate is not
      called; a verify denial is returned uncharged; a refusing hook is
      answered uncharged with the gate's charge never called; the hook
      receives the offering's terms and the verified key's terms and digest; a
      verified charge is what `charge` is called with and the default is used
      when none; the upstream request carries the deployment's credential and
      never the buyer's; `/v1/models` lists one model; two offerings — one
      projected the way an API-credits composition would (a service name, a
      configured charge, no terms) and one the way inference's root does —
      behave identically save their values (api-family delta scenario "Two
      domains front model servers", the in-process half).
- [ ] 4.6 Integration tests (`domains/api/gateway/tests/integration/`): the
      real gateway app over `httpx.ASGITransport` with a scripted authority
      (the gate's `TokensClient` against a recorded verify and consume
      service, as the gate's conformance runner scripts one) and a controlled
      upstream that releases its streamed events on a trigger, asserting the
      first event reaches the client before the upstream sends the last
      (inference delta scenario "A completion is streamed") — this one case
      against the app served by uvicorn in a thread on an ephemeral port,
      because `httpx.ASGITransport` joins the body parts after the app
      returns and cannot observe an early event (plan review 06 F4) — a
      non-streamed
      response is relayed with its status and body, and an admitted request is
      charged exactly once. The gateway has no typed client of its own: the
      OpenAI version-1 wire shape is its contract, so these tests speak it
      directly and are commented as such (`docs/development/TESTING.md`,
      "Typed client contract verification").
- [ ] 4.7 Build and release: `domains/Makefile` gains `dist-api-gateway`
      (after `dist-api-gate`) and `test-api-gateway`, both in its `dist` and
      `test-api` aggregates; the root `Makefile` gains `dist-api-gateway` and
      `test-api-gateway` (building the wheels the project installs, then
      `require-wheels`, as `test-api-gate` does); `.github/workflows/tests.yml`
      gains an `api-gateway` matrix row with `predist`;
      `manifests/published-distributions.json` gains `api-gateway` after
      `api-gate`; `.github/workflows/publish-pypi.yml` gains its filter and
      matrix entries; `docs/development/RELEASING.md`'s "Published packages"
      table gains its row (`scripts/tests/test_publish_matrix.py` holds the
      three in agreement).
- [ ] 4.8 **Verification.** `make test-api-gateway` (unit and the library's
      integration level); `make test-release-tooling` for the publish-matrix
      tests; `make check-architecture` for the domain-import rule. `make
      test`. New project: `make lock PROJECTS=domains/api/gateway` and `make
      check-packaging`. Once deployed, `e2e_inference_deal` exercises the
      library through the inference gateway image (sections 8 and 11); no
      API-credits deployment composes it, and none is owed by this change.

## 5. Inference storefront `arkhai-inference-storefront`

Delivers the `inference-storefront` executable on the `kit/storefront` shell:
the selling contributions, the model-card publication mapping, the issuance
projection with accepted terms, the request-priced guard, the public result
carrying the contract's materialization, the Alkahest-only stage table and
startup refusal, the kit's seller round hook, the recovered modules, and the
development seed (D1, D3, D6, D7, D8, D9, D13, D17; review 02 F1 as amended by
review 04; inference delta "Inference roles are composed from independent
distributions", "Alkahest is the only inference settlement mechanism",
"Issuance identifiers are inference-labelled and agree across the boundary",
"Inference state is isolated", "Quota-backed publication", "The issuance
projection names the served model and pins the accepted terms", "The
delivery's public result carries the accepted card", "Only request-priced rate
cards are publishable without metered consumption").

- [ ] 5.1 Create `domains/inference/storefront/` with `pyproject.toml`
      (`arkhai-inference-storefront`, hatchling, `packages =
      ["src/inference_storefront"]`, console script `inference-storefront`,
      entry point `market.storefront_domains` → `inference =
      "inference_storefront.domain_runtime:INFERENCE_STOREFRONT_DOMAIN"`),
      depending on what `domains/apicredits/storefront/pyproject.toml`
      declares less `arkhai-api-selling-arkhai-payments` and with
      `arkhai-inference-domain` in place of the API-credits domain (D9:
      neither inference wheel declares the fiat payments distribution; D6), a
      `Makefile` with `reinit` and `test`, `src/inference_storefront/settings.toml`,
      and `tests/unit/` and `tests/integration/` roots. The architecture check
      reads `domains/inference/storefront` as an executable through its role
      word.
- [ ] 5.2 `src/inference_storefront/container.py`: `SELLING_CONTRIBUTIONS =
      SellingContributions(label=IssuanceLabel("inference"), kind=INFERENCE_KIND,
      offering_mode="inference", contribution_id="inference",
      table_prefix="inference", listing_schema=InferenceListing,
      publication_mapping=<5.3>, issuance_projection=<5.4>,
      consumption_rule=ConsumptionRule.FIXED_PER_REQUEST,
      publication_guards=(<5.5>,), public_result_extension=<5.6>,
      refusal_noun="inference")` (D6); the registry and settlement collaborators
      the API-credits container builds, with `ALKAHEST_STAGE` the only entry of
      `SELLER_STAGES` (D9) and the settlement composition the kit's
      `SellingSettlementComposition` over that table, its obligation list
      unmodified (D17; inference delta "The storefront's settlement composition
      MUST be the kit's obligation list unmodified").
- [ ] 5.3 `src/inference_storefront/model_card.py`, recovered from the
      withdrawn branch at f76a06ce3 and adapted to the kit's
      `PublicationMapping` signature (D13, D7): a `PublishFromQuotaRequest`
      subclass of the kit's with a `model_card` object, and
      `publication_mapping(request, quota)` validating
      `request["model_card"]` as `InferenceModelCard` with `resource_id`,
      `capacity_site_id`, and `offering_mode` filled from the `QuotaSource`,
      so a card cannot name another resource than its quota backs; the kit's
      `ListingSeed` passes the seed's `[seed.model_card]` table through as that
      field.
- [ ] 5.4 `src/inference_storefront/container.py` (or `issuance.py` beside
      it): `issuance_projection(listing_resource)` returning
      `IssuanceSubject(service=card.served_model_name,
      resource_id=card.resource_id, endpoint=card.endpoint.base_url,
      accepted_terms={"rate_card": ..., "attestation": ...} as canonical JSON
      of the accepted card's two fields, terms_digest=<sha256 of that
      payload>, request_charge=card.rate_card.request_credits)` (D1; review 02
      F1; review 04 F1 and F2; inference delta "The issuance projection names
      the served model and pins the accepted terms").
- [ ] 5.5 `src/inference_storefront/rate_card_guard.py`, recovered from the
      withdrawn branch at f76a06ce3 and adapted to the kit's `PublicationGuard`
      signature (D13, D8): one function returning why a card whose prompt,
      cached-prompt, completion, or image rate is non-zero may not be
      published, naming the field, or `None`; the one entry of
      `publication_guards`, which `meter-inference-usage` deletes. The
      predicate it applies, `non_request_priced_rate(card) -> str | None`
      naming the offending field — a non-zero per-token or image rate, or a
      `request_credits` of zero or above `2**53 - 1` (plan review 06 F3 as
      amended by 07 F1; inference delta scenario "A free request rate is
      configured") — is
      added to
      `domains/inference/src/arkhai_inference/listings/pricing.py` with a unit
      test in `domains/inference/tests/`, because the gateway executable (8.3)
      applies the same rule and two composition roots cannot import each other
      (D8).
- [ ] 5.6 `src/inference_storefront/materialization.py`, recovered from the
      withdrawn branch at f76a06ce3 and reduced to the kit's
      `PublicResultExtension` (D13, D3): `public_result_extension(listing_resource,
      result, delivery)` returning, under the one key `materialization`, the
      contract's `InferenceMaterialization` with `listing_resource` the
      accepted card, `rate_card` that card's, `quantity`, `key_mode`, and
      `key_id` from the result, `fulfillment_id` the result's,
      `mechanism` the context's, and `escrow_uid` the context's
      `settlement_ref` (1.5; D3 "The third input is new to the kit"),
      serialised as plain JSON and carrying no secret (the kit's
      `public_extension` refuses otherwise). The withdrawn module's own
      accepted-rate-card repository, migration, and artifact slot are not
      recovered: the kit records the accepted listing itself (D3 "No
      acceptance hook is needed").
- [ ] 5.7 `src/inference_storefront/startup_refusal.py`: the API-credits
      root's refusals (retired settings, capacity configuration) plus one new
      heading refusing any `[settlement].priority` entry `SELLER_STAGES` lacks,
      naming the mechanism, before the signer is resolved or a loop starts
      (D9; inference delta scenario "Another mechanism is configured"). The
      kit ignores an unknown mechanism, so this refusal is the new piece.
- [ ] 5.8 `src/inference_storefront/{server,domain_runtime,cli,settlement_composition}.py`
      and `controllers/`: the composition the API-credits root performs —
      services, the negotiation runtime with the kit's
      `default_seller_round_hook` (the proposal's "the kit's seller round
      hook"; no inference policy is added), the listing service, the system
      service, the route bindings, the lifespan, `serve`, `publish`, and
      `listings` commands — each carrying only inference's values; the
      `market.storefront_domains` contract is `arkhai_inference.domain_runtime.market_domain()`
      with the storefront capability (inference delta "Inference roles are
      composed from independent distributions"). `listing_seed()` passes
      `pool_id="default"`, the Alkahest stage's seed escrow settings, and the
      storefront's own SQLite database path (D6; inference delta "Inference
      state is isolated").
- [ ] 5.9 `domains/inference/storefront/storefront.inference.toml`: the
      development configuration on `storefront.credits.toml`'s pattern with
      `[settlement].priority = ["alkahest.v1"]` and no payments section, the
      inference registry and the inference authority as its `[registry]`,
      `[credits]`, and `[capacity.sites.default]`, and the `[seed]` and
      `[seed.model_card]` tables recovered from the withdrawn branch at
      f76a06ce3 (quota `total_units` large, `request_credits = 1`, token and
      image rates zero, endpoint the gateway's base URL) (D10's storefront
      file; D13; the "Quota as a sales cap" risk). Identity pins are filled in
      section 10 when the identities exist.
- [ ] 5.10 `domains/inference/storefront/Dockerfile` on the API-credits
      storefront's pattern: lock-driven install through `uv_project.py image`
      and `install-wheel`, no source copy, `XDG_CONFIG_HOME=/etc`, its own
      `/app/data` volume (inference delta "Inference state is isolated";
      `BUILD_AND_PACKAGING.md`, "Images").
- [ ] 5.11 Unit tests (`tests/unit/`): the contribution values of 5.2
      (`test_contributions.py`); the publication mapping fills the three
      quota fields and refuses a card naming another resource
      (`test_model_card.py`); the projection's digested service is the served
      model name, its endpoint the card's base URL, and its three accepted-terms
      values the card's rate card and attestation, so two cards sharing a
      `model_id` under different served names project different services
      (`test_issuance_projection.py`; inference delta scenario "Two listings of
      one model are purchased"); the guard names the non-zero field, accepts
      a `request_credits` of `2**53 - 1`, and refuses `2**53` naming the
      field, so publication refuses it before canonicalization (plan review
      07 F4; `test_rate_card_guard.py`); the public extension's materialization
      validates against the listing it carries and refuses a card other than
      the listing's (`test_materialization.py`); `SELLER_STAGES` holds Alkahest
      alone and the wheel's requirements name no fiat payments distribution
      (`test_settlement_composition.py`; inference delta scenario "Role wheels
      are inspected"); no module under `inference_storefront` imports an
      API-credits module, including under `TYPE_CHECKING`, on
      `domains/bare_metal/storefront/tests/test_import_boundaries.py`'s pattern
      (`test_import_boundaries.py`; inference delta scenario "A sibling domain
      is imported").
- [ ] 5.12 Application-integration tests through the typed client
      (`tests/integration/`, the real storefront app over ASGI with the
      storefront client and a scripted authority at the external boundary):
      a seller publishes a model-card listing from its quota and the registry
      publication carries the card (`test_publish_reconcile.py`; inference
      delta "Quota-backed publication" scenarios: zero quota refused, sold out
      closes and replenished republishes); a per-token rate card is refused
      naming the field and nothing is published (`test_rate_card_refusal.py`);
      a configuration naming a second mechanism fails startup naming it before
      any request is served (`test_startup_refusal.py`); a settled negotiation's
      public result carries `materialization` with the rate card in force at
      acceptance after the listing is republished at another rate
      (`test_materialization_delivery.py`; inference delta scenario "The seller
      reprices between acceptance and fulfillment"); the issuance request the
      storefront sends carries the accepted terms, digest, and charge and the
      `inference` label (`test_issuance_request.py`).
- [ ] 5.13 Build and release: `domains/inference/Makefile` becomes the
      per-role aggregate on `domains/apicredits/Makefile`'s shape
      (`test: test-domain test-storefront ...`); `domains/Makefile` and the
      root `Makefile` gain `dist-inference-storefront` (depending on the family
      wheels it installs) and `test-inference-storefront`, in the `dist`,
      `test-inference`, and root `test` aggregates; `.github/workflows/tests.yml`
      gains `inference-storefront`; `manifests/published-distributions.json`,
      `.github/workflows/publish-pypi.yml`, and `docs/development/RELEASING.md`
      gain `arkhai-inference-storefront` after the family distributions it
      depends on.
- [ ] 5.14 **Verification.** `make test-inference-storefront` (unit and
      application integration through the typed client); `make test-inference`
      (the domain package's unit level, unchanged); `make test-release-tooling`.
      `make test`. New project: `make lock PROJECTS=domains/inference/storefront`
      and `make check-packaging`, whose architecture check classifies the root
      as an executable of the `inference` domain in the `api` family. Once
      deployed, `e2e_inference_deal` exercises publication, the pinned terms,
      and the public result; the startup refusal and the guard are proven in
      process and none is owed in the lane.

## 6. Inference service root `arkhai-inference-service`

Delivers the `arkhai:inference-service` image: the family authority composed
under the `inference` label with its own capacity profile, database, key
prefix, and migration chain (D6, D14, D15; api-family requirement "Each domain
composes the authority kit in its own service root"; inference delta
"Issuance identifiers are inference-labelled and agree across the boundary",
"Inference state is isolated", "Bearer credential is delivery, not identity or
payment authority").

- [ ] 6.1 Create `domains/inference/service/` with `pyproject.toml`
      (`arkhai-inference-service`, hatchling, `packages =
      ["src/inference_service"]`) declaring what
      `domains/apicredits/service/pyproject.toml` declares, with the same
      `[tool.arkhai.architecture.runtime-dependencies]` reason for the
      identity kit; a `Makefile` with `reinit` and `test`; `src/inference_service/settings.toml`
      under the environment prefix `INFERENCE_`; `tests/unit/` and
      `tests/integration/`.
- [ ] 6.2 `src/inference_service/config.py`: `ISSUANCE_LABEL =
      IssuanceLabel("inference")` (fulfilment prefix `inference-fulfillment.v1`
      by default), `CAPACITY_PROFILE = CapacityProfile(offering_mode="inference",
      pool_provider="inference", pool_id="default", pool_label=..., deliverable_modes
      and advertisable_modes {"inference"}, backing=BACKED)`, and
      `authority_config = AuthorityConfig(label, profile, database_url=settings.database_url,
      distribution="arkhai-inference-service", key_prefix="ik")` (D6; the
      inference delta's "A key is issued" scenario: the `ik` prefix).
- [ ] 6.3 `src/inference_service/{container,main,identity}.py` and
      `controllers/{keys_controller,system_controller}.py`: the API-credits
      root's composition — engine, `run_migrations` then `initialize` at
      startup (D15: the family chain from its first step, on the inference
      database), `KeysService` and `AuthorityRouteService`, the site kit's
      signed authentication over the adapted route declarations with the
      storefront trusted as `seller` and the gateway as `service` (D14), and
      the routers forwarding the optional scope and terms fields as section
      2.6 does.
- [ ] 6.4 `domains/inference/service/Dockerfile` on the API-credits service's
      pattern, with `INFERENCE_DATABASE_URL` defaulting to
      `sqlite:////app/data/inference.db` on its own named volume and a port
      distinct from the API-credits service's (inference delta "Inference state
      is isolated").
- [ ] 6.5 Unit tests (`tests/unit/test_config.py`): the label, profile, prefix,
      and distribution of 6.2; the profile's pool policy tags. The route-contract
      coverage test the API-credits service carries
      (`test_route_contract_coverage.py`), bound to this root's routers.
- [ ] 6.6 Application-integration tests through the typed client
      (`tests/integration/test_canonical_client.py`, the real app over ASGI
      through `AuthorityClient` for issuance and the gate's `TokensClient` for
      verify and consume, the quota registered through the site client as the
      API-credits round-trip test does): an issuance for 2,000,000 credits
      yields a key with that balance and an `ik_` identifier whose request
      digest equals `issuance_request_digest` under the inference label and
      differs from the API-credits label's for the same inputs (inference delta
      scenarios "A purchased balance is issued", "The same request is digested
      on both sides", "A key is issued"); `verify` returns the pinned
      `request_charge`, digest, and terms; a top-up of that key under other
      terms, or from another `(service, resource_id)`, is refused
      `key_out_of_scope` with the balance unchanged; `verify` with another
      offering's scope is refused uncharged (inference delta scenario "A buyer
      tops up from another model's listing", the authority half); an
      API-credits-labelled issuance request is refused by schema, and a bearer
      secret presented where a marketplace signature is required is refused as
      unauthenticated (inference delta "Inference state is isolated", "Bearer
      credential is delivery, not identity or payment authority").
- [ ] 6.7 Build and release: `domains/Makefile` and the root `Makefile` gain
      `dist-inference-service` (after `dist-api-authority`) and
      `test-inference-service` in the aggregates; `build-inference-service`
      (`arkhai:inference-service`) in the root `Makefile` and in `build`;
      `.github/workflows/tests.yml` gains `inference-service`; the manifest,
      publish workflow, and `RELEASING.md` gain `arkhai-inference-service`.
- [ ] 6.8 **Verification.** `make test-inference-service` (unit and
      application integration through the typed client). `make test`. New
      project: `make lock PROJECTS=domains/inference/service` and `make
      check-packaging`. Once deployed, `e2e_inference_deal` exercises
      issuance, verification with pinned terms, consumption, and the scope
      refusal; the digest-difference and bearer-refusal cases are proven in
      process and none is owed in the lane.

## 7. Inference buyer plugin `arkhai-inference-buyer`

Delivers the `market inference` command group: the buying contributions,
model-card rendering, the Alkahest-only stage table, the purchase-time
verification hook, and the surfaced scope refusal (D9, D12, D16; review 01 F4
"The buyer plugin surfaces the refusal rather than retrying"; inference delta
"The buyer plugin discovers by model card under the inference schema",
"Alkahest is the only inference settlement mechanism", "The gateway and buyer
carry verification seams for a later proof"; market-composition delta
"Versioned market-domain contract", scenario "Shipped domains are loaded").

- [ ] 7.1 Create `domains/inference/buyer/` with `pyproject.toml`
      (`arkhai-inference-buyer`, hatchling, `packages =
      ["src/arkhai_inference_buyer"]`, entry point `market.buyer_domains` →
      `inference = "arkhai_inference_buyer.cli:domain"`) depending on `typer`,
      `arkhai-api-buying`, `arkhai-api-buying-alkahest`,
      `arkhai-inference-domain`, `arkhai-core-buyer`, `arkhai-core`, and not on
      `arkhai-api-buying-arkhai-payments` (D9); a `Makefile` with `reinit` and
      `test`; `tests/`.
- [ ] 7.2 `src/arkhai_inference_buyer/cli.py`: `CONTRIBUTIONS =
      BuyingContributions(schema_id="inference",
      provision_terms=InferenceProvisionTerms, command="inference",
      command_help=..., noun="inference", resource_query_example=<a model_id
      and quantization example>, rendering=ListingRendering(resource=coerce_resource_dict,
      summary_header="Model", summary=<the model identity>, columns=(quantization,
      context length, provenance, request charge), details=<the card's fields>))`
      (D12); `SETTLEMENT = BuyerSettlementComposition(CONTRIBUTIONS,
      SettlementStageTable({AlkahestBuyerStage}))` with Alkahest the only
      stage (D9); `command_group(SETTLEMENT)` registered as `market inference`
      with `listing list|show`, `buy`, `negotiate`, `settle`, and `settlement
      status`; `domain` the contract from `arkhai_inference.domain_runtime.market_domain()`
      with the buyer capability, `make_inference_provision_terms`, and the
      configured policy, as the API-credits plugin builds its own. Discovery
      filters compile from the served specification and the plugin encodes no
      rate-bound pairing (D12; inference delta scenario "Buyer bounds a rate
      without naming an asset").
- [ ] 7.3 `src/arkhai_inference_buyer/verification.py`: the purchase-time
      hook — called with the attestation envelope of the listing being bought,
      before settlement is proposed, returning a refusal or `None` — and its
      `admit_all` default, applied as a plugin-local wrapper around the
      Alkahest stage's `propose` so the library is unchanged (D16; inference
      delta "The gateway and buyer carry verification seams for a later
      proof"). No proof `kind` is defined.
- [ ] 7.4 The authority's `key_out_of_scope` refusal of a top-up, relayed by
      the storefront's settlement refusal, is reported by `market inference
      buy --key-id` as the storefront names it and is not retried (review 01
      F4; inference delta scenario "A buyer tops up from another model's
      listing", the buyer half). A completed purchase shows the key, the base
      URL, and the served model name from the kit's connection payload
      (inference delta scenario "A buyer completes a purchase").
- [ ] 7.5 Unit tests (`tests/`): `test_plugin_export.py` — the entry point
      loads the `inference.v1` contract once with the buyer capability and the
      `inference` schema identity; `test_listing_helpers.py` — the rendering's
      summary and columns from a card; `test_discovery_routing.py` — with
      compute, API-credits, and inference registries configured, only the
      registry declaring `inference` is queried for a `model_id` filter, and a
      rate bound without `rate_card_asset` is refused before sending when
      compiled against `domains/inference/registry/filter-spec.yaml` (inference
      delta scenario "A buyer searches by model"); `test_settlement_composition.py`
      — one stage, Alkahest, and no payments distribution among the wheel's
      requirements; `test_verification_hook.py` — the hook runs before
      `propose` with the listing's envelope, a refusal stops the proposal, and
      the default admits so behaviour equals the unwrapped stage; `test_scope_refusal.py`
      — a scripted storefront refusal naming the key's scope reaches the
      command's output once; `test_packaging.py` on the API-credits buyer's
      pattern.
- [ ] 7.6 `core/tests/unit/test_domain_boundaries.py`: `CONCRETE_IDENTITIES`
      gains `inference.v1`, so core is checked for branches on the new identity
      (market-composition delta scenario "Shipped domains are loaded";
      `market-composition` requirement "Schema-opaque core orchestration"). The
      installed-plugin half of that scenario is the end-to-end image, which
      installs every shipped buyer plugin (section 11).
- [ ] 7.7 Build and release: `domains/Makefile` and the root `Makefile` gain
      `dist-inference-buyer` (after `dist-api-buying-alkahest`) and
      `test-inference-buyer` in the aggregates; `.github/workflows/tests.yml`
      gains `inference-buyer`; the manifest (`wheel_only`, as the API-credits
      buyer is), publish workflow, and `RELEASING.md` gain
      `arkhai-inference-buyer`.
- [ ] 7.8 **Verification.** `make test-inference-buyer` (unit); `make
      test-core` for the boundary test. `make test`. New project: `make lock
      PROJECTS=domains/inference/buyer` and `make check-packaging`. Once
      deployed, `e2e_inference_deal` exercises discovery with three registries
      configured, `buy`, settlement, the delivered credential, and the top-up;
      the hook and the scope refusal's rendering are proven in process.

## 8. Inference gateway executable `arkhai-inference-gateway-service`

Delivers the `arkhai:inference-gateway` image: the root that reads and
validates the listing it fronts, projects the family's offering, supplies the
upstream and the `service`-role signing credential, and is built from
digest-pinned inputs (D2; review 01 F1 as amended by review 02 F1; review 02
F3; D14; D16; inference delta "The gateway admits only paid requests for
listed models", "The gateway and buyer carry verification seams for a later
proof").

- [ ] 8.1 Create `domains/inference/gateway-service/` with `pyproject.toml`
      (`arkhai-inference-gateway-service`, hatchling, `packages =
      ["src/inference_gateway_service"]`) depending on `arkhai-api-gateway`,
      `arkhai-api-gate[signed]`, `arkhai-inference-domain`, the client of the
      listing source (8.2), and `uvicorn`; a `Makefile`; `tests/unit/` and
      `tests/integration/`. The architecture check reads the directory as an
      executable through the role word after its last hyphen (D2; `ARCHITECTURE.md`,
      "Package and dependency layers").
- [ ] 8.2 `src/inference_gateway_service/config.py`: settings under the prefix
      `INFERENCE_GATEWAY_` — the gate's `GateConfig.from_env(prefix,
      authority_label="inference-service")` set (authority URL, the
      `service`-role identity credential file, authority principals, verify
      TTL, timeouts), plus the `STOREFRONT_URL`, the `RESOURCE_ID` and
      `SERVED_MODEL_NAME` that select the listing, an optional `LISTING_ID`
      override, the `UPSTREAM_BASE_URL`, and the `UPSTREAM_CREDENTIAL_FILE`.
      The listing is read from the inference storefront, the listing's
      origin, through the core storefront client (D2: the storefront is the
      default source; a registry read is admitted but not built here).
- [ ] 8.3 `src/inference_gateway_service/offering.py`: `load_offering(settings)`
      selects the listing — the configured id when set, otherwise the
      storefront's open listings, every page at the route's largest size
      until a short page, filtered to the one whose card names the
      configured `resource_id` and served model, none or several refusing
      readiness with the count (plan review 06 F1; 07 F3; inference delta
      scenario "The gateway starts before the storefront has published") — and
      `main.py` retries the load on a short interval until it succeeds,
      `/health` reporting not ready until then; it validates the listing as
      `InferenceListing`, requires the
      card to be request-priced through the contract's
      `non_request_priced_rate` (5.5; D8), the storefront guard's own
      predicate, and returns
      `GatewayOffering(service=card.served_model_name,
      resource_id=card.resource_id, default_charge=card.rate_card.request_credits,
      purchase=PurchasePointer(service_name=served_model_name, listing_id,
      storefront_url, registry_url), upstream_base_url, upstream_credential_file,
      current_terms={"rate_card": ..., "attestation": ...})` — the same
      canonical payload the storefront's projection pins, so the hook's
      comparison is like for like (review 01 F1; review 02 F3; review 02 F2).
      Readiness refuses a listing that cannot be read or a card that is not
      request-priced, naming the cause.
- [ ] 8.4 `src/inference_gateway_service/main.py`: builds the `TokenGate`
      from the gate configuration with `scope_service` and `scope_resource_id`
      from the offering and `amount_per_request` its default charge, signs
      toward the authority as the `service` role with the gateway's own
      credential (D14), composes `create_gateway_app(offering, gate,
      verification=admit_all)` (D16), and serves it under uvicorn; `/health`
      reports the offering loaded.
- [ ] 8.5 `domains/inference/gateway-service/Dockerfile`: the lock-driven
      two-stage pattern with every `FROM` in the form
      `python:${PYTHON_VERSION}-slim@sha256:<digest>` — the tag the
      Python-version check requires, pinned to the digest it resolved to when
      written, which `scripts/check_python_version.py` accepts since it flags
      only a literal version in the tag — no source copy, the credential files
      read from `/run/secrets/arkhai/`, and the upstream credential from a
      mounted secret (D16 "built reproducibly from a digest-pinned base";
      inference delta "the gateway image MUST be built from digest-pinned
      inputs"; `BUILD_AND_PACKAGING.md`, "Images").
- [ ] 8.6 Unit tests (`tests/unit/`): the projection of a fixture listing
      (`test_offering.py`) — service, scope, default charge, purchase pointer,
      and the canonical terms payload equal to the storefront projection's
      digest input for the same card; the selection over a scripted listing
      list — one match selected, none and two refused with the count, the
      sole match and a second duplicate each on a later page (plan review 07
      F3), the configured id taking precedence; readiness refusals for an
      unreadable listing, a per-token card, and a card whose `request_credits`
      is `2**53`, refused before the terms payload is canonicalized, with
      `2**53 - 1` accepted (plan review 07 F4); the gate configuration's scope
      and charge
      (`test_config.py`); every `FROM` in the Dockerfile carries `@sha256:`
      (`test_dockerfile.py`).
- [ ] 8.7 Integration tests (`tests/integration/test_gateway_against_authority.py`,
      the gateway app projected from a fixture listing, the real inference
      service root in process as the authority with a quota registered and a
      pinned key issued through `AuthorityClient`, and a controlled upstream at
      the external boundary; `arkhai-inference-service` is a test-only
      dependency, as the API-credits storefront's tests install the buyer): an
      admitted request is charged the key's pinned `request_charge`; a key
      issued under another offering's `(service, resource_id)` is `403` with
      the upstream untouched and the balance unchanged; an unlisted model is
      `404` with no authority call; exhaustion is `402` carrying the storefront
      and registry; a republished default charge does not change what an
      existing key pays (api-family delta scenario "The seller reprices after a
      sale", in process); a streamed response reaches the client before the
      upstream finishes, this case against the app on a socket as 4.6 runs it
      (plan review 06 F4).
- [ ] 8.8 Build and release: `domains/Makefile` and the root `Makefile` gain
      `dist-inference-gateway` (after `dist-api-gateway`) and
      `test-inference-gateway-service` in the aggregates;
      `build-inference-gateway` (`arkhai:inference-gateway`) in the root
      `Makefile` and in `build`; `.github/workflows/tests.yml` gains
      `inference-gateway-service`; the manifest, publish workflow, and
      `RELEASING.md` gain `arkhai-inference-gateway-service`.
- [ ] 8.9 **Verification.** `make test-inference-gateway-service` (unit and
      the application's integration level against the in-process authority).
      `make test`. New project: `make lock PROJECTS=domains/inference/gateway-service`
      and `make check-packaging`. Once deployed, `e2e_inference_deal`
      exercises every status this section names through the real stub and
      authority.

## 9. Deterministic model stub and the `vllm` profile

Delivers the OpenAI-style model server the lane runs without a GPU or a
download, and the Compose profile that swaps in a real server (D5;
deployment-state delta "Local inference stack composition", scenario "A real
model server is wanted locally"; test-compatibility delta "The scenario MUST
run against a deterministic model server").

- [ ] 9.1 Create `e2e-tests/model-stub/` beside the end-to-end image, outside
      the architecture check (`ARCHITECTURE.toml` skips `e2e-tests`): a
      `pyproject.toml` (one package under `src/`, `fastapi` and `uvicorn`), a
      `Makefile` with `reinit` and `test`, and `src/inference_model_stub/app.py`
      answering `GET /v1/models` (one configured model), `POST /v1/chat/completions`,
      and `POST /v1/completions` with responses keyed deterministically on
      the prompt, streamed as server-sent events with a small inter-chunk delay
      when `stream` is set, and `/health` (D5). It is not a published
      distribution: like the end-to-end image, it is test tooling, so it joins
      neither the manifest nor the publish workflow.
- [ ] 9.2 `e2e-tests/model-stub/Dockerfile` building `arkhai:inference-model-stub`
      on the lock-driven pattern; root `Makefile` targets
      `dist-inference-model-stub` and `build-inference-model-stub`
      (the proposal's "Build" list), the latter in `build-e2e-inference`
      (section 11).
- [ ] 9.3 `domains/inference/compose.yml` (created in section 10 if this
      section lands first): the `model-stub` service on the default profile,
      and a `model-server` service under `profiles: [vllm]` running the CPU
      vLLM image and small instruct model `docs/cookbooks/vllm-apicredits-seller.md`
      names, with the gateway's upstream switched to it by the profile and no
      other service's configuration changed (D5; deployment-state delta
      scenario "A real model server is wanted locally").
- [ ] 9.4 Unit tests (`test_app.py` under `e2e-tests/model-stub/tests/`, the
      stub over ASGI): the model list, an exact non-streamed completion for a known
      prompt, and a streamed one whose first event precedes the last; the
      stub rejects a `model` it is not configured for with `404`, so the
      gateway's own check is observable as the one that answers first.
- [ ] 9.5 **Verification.** `make -C e2e-tests/model-stub test` (unit),
      wired into `make test-e2e-unit`. `make test`. New project: `make lock
      PROJECTS=e2e-tests/model-stub` and `make check-packaging`. Once deployed,
      `e2e_inference_deal` runs against the stub; the `vllm` profile is not
      exercised by any lane, by D5, and none is owed.

## 10. Compose stack, development identities, and build targets

Delivers the inference stack's topology, overlays, identities, environment
targets, and aggregate targets (D6, D10; deployment-state delta "Local
inference stack composition"; `dev-env/identities/README.md`'s derivation
rule; `scripts/tests/test_lane_compose.py` and
`e2e-tests/tests/unit/test_domain_stack_configuration.py`, which pin each
stack's shape).

- [ ] 10.1 `domains/inference/compose.yml`, topology only (D10): `inference-registry`
      (`arkhai:registry` with `REGISTRY_FILTER_SPEC_PATH=/app/filter-spec-inference.yaml`,
      which the image already carries, so no bind mount; its own
      `REGISTRY_AUTHORITY_*` identity and descriptor; deployment-state delta
      "a registry instance selecting the packaged `inference` filter
      specification by path"), `inference-service` (`arkhai:inference-service`,
      its signing credential and admin key from `/run/secrets/arkhai/`),
      `model-stub` and the `vllm` profile's `model-server` (section 9),
      `inference-gateway` (`arkhai:inference-gateway`, `INFERENCE_GATEWAY_VERIFY_TTL_SECONDS=3`
      as the API-credits sample app sets, per review 01 F2; the storefront
      URL, the seed's `resource_id` and served model name selecting its
      listing, no listing id; the upstream and credential files), and
      `inference-storefront`
      (`arkhai:inference-storefront` with `storefront.inference.toml` mounted at
      `/etc/arkhai/storefront.toml`); named volumes `inference-service-data`
      and `inference-storefront-data`; every credential a `${VAR:?...}`-guarded
      mount (deployment-state delta scenario "A development credential is
      missing"); no credential value committed.
- [ ] 10.2 `compose.inference.yml` including `compose.dev.yml` and the domain
      file; `compose.inference-local.yml` binding the identities of 10.3, the
      storefront's wallet key, and a one-shot `inference-buyer-cli` under the
      `buyer` profile on `credits-buyer-cli`'s pattern; `compose.inference-lane.yml`
      adding the lane-only `compute-registry` and `api-credits-registry`
      (D10, D11: present only for the schema-filter scenario); root
      `docker-compose.yml` includes `domains/inference/compose.yml`
      (deployment-state delta scenarios "The full stack is brought up", "The
      inference stack is brought up alone").
- [ ] 10.3 `dev-env/identities/`: `inference-registry.ed25519`,
      `inference-service.ed25519`, `inference-gateway.ed25519` derived by the
      README's rule (checking no derived identifier begins with `-`),
      `inference.identity.env` and `inference.wallet.env` on the lowest
      numbered Anvil development account the README's assignment tables show
      no storefront using, `inference-admin-key`, and
      `inference-buyer.config.toml` pinning the inference registry's
      principal; the public identifiers pinned where they are consumed —
      `domains/inference/compose.yml`, `storefront.inference.toml`'s registry
      and site authority sections, and the buyer configuration (D10; the
      README's "What this directory has to satisfy"; `AGENTS.md`, "Test
      fixtures and local development configuration": each env file states it
      is a development value never for a public network).
- [ ] 10.4 Root `Makefile`: `e2e-inference-stack-env` printing
      `INFERENCE_REGISTRY_IDENTITY_CREDENTIAL_FILE`, `INFERENCE_IDENTITY_ENV_FILE`,
      `INFERENCE_EVM_WALLET_ENV_FILE`, `INFERENCE_ADMIN_KEY_FILE`,
      `INFERENCE_SERVICE_IDENTITY_CREDENTIAL_FILE`,
      `INFERENCE_GATEWAY_IDENTITY_CREDENTIAL_FILE`, `INFERENCE_BUYER_CONFIG_PATH`,
      `INFERENCE_BUYER_CREDENTIAL_FILE`, `INFERENCE_BUYER_PROFILE_DIR`, and
      `INFERENCE_BUYER_STATE_DIR`; `e2e-inference-dev-env` adding the lane
      registries' credential files; `e2e-dev-identities-env` gaining the
      stack (D10). `build-inference-storefront`, `build-inference-service`,
      `build-inference-gateway`, and `build-inference-model-stub` join `build`;
      `dist-inference-*` (sections 5–9) are in `dist`; `test-inference-*` in
      `test`.
- [ ] 10.5 `scripts/tests/test_lane_compose.py`: `STACKS` gains `inference`
      (`e2e-inference-dev-env`, `simple-market-inference`, the three files)
      and the full stack's overlay list gains `compose.inference-local.yml`;
      cases that the inference lane composes its own compute and API-credits
      registries, that the full stack has one chain and three registries and
      no lane registry, that the inference wrapper alone composes no VM or
      API-credits service, that no inference storefront carries a provisioning
      mode, and that an unset credential fails the render naming the variable.
      `e2e-tests/tests/unit/test_domain_stack_configuration.py`: no committed
      inference admin credential, independent named volumes, and the
      storefront and gateway runtimes installed from the staged wheel only.
      `scripts/tests/test_multi_storefront_compose.py`: the inference
      storefront's authority pins are isolated from the others'.
- [ ] 10.6 Bring the inference wrapper up locally with
      `make e2e-inference-dev-env` and the three files, then the full stack
      with `make e2e-dev-identities-env`, and record in the section note that
      three registries serve three schema identities and the inference
      authority, gateway, stub, and storefront report healthy, without a GPU
      or an external fetch (deployment-state delta scenarios; the `vllm`
      profile is not brought up).
- [ ] 10.7 **Verification.** `make test-release-tooling` (the lane-compose,
      multi-storefront, and publish-matrix tests, unit level) and `make
      test-e2e-unit` (the stack-configuration tests). `make test`. No lock
      changes here; `make check-packaging` runs for `check-uv-setup`'s
      Dockerfile and Makefile rules over the new images. Once deployed,
      `e2e_inference_deal` runs on this stack; the "brought up alone" and
      "full stack" scenarios are the render tests above and 10.6's record,
      and none is owed in a lane.

## 11. End-to-end lane and the `e2e_inference_deal` scenario

Delivers the inference lane, its workflow job, marker, settings, and the deal
scenario over the domain-neutral helpers (D11; review 01 F2; test-compatibility
delta "Inference end-to-end deal path"; the inference delta's gateway and buyer
scenarios; test-compatibility requirement "A deployable domain's deal runs on
every end-to-end run").

- [ ] 11.1 `e2e-tests/Makefile`: `E2E_INFERENCE_ENV`, `E2E_INFERENCE_PROJECT :=
      simple-market-inference`, `E2E_INFERENCE_COMPOSE` over
      `compose.inference.yml`, `compose.inference-local.yml`, and
      `compose.inference-lane.yml`, `E2E_INFERENCE_MODULE ?= e2e_inference_deal`,
      and `test-e2e-inference`, `e2e-inference-down`, `e2e-inference-logs` on
      the API-credits lane's pattern; root `Makefile` `build-e2e-inference`
      (`build-e2e-base`, `build-registry`, the four inference images); `.github/workflows/e2e.yml`
      gains an `e2e-inference` job mirroring `e2e-apicredits` (D11).
- [ ] 11.2 `e2e-tests/pyproject.toml`: the marker `e2e_inference_deal` with
      its one-line description, and `arkhai-inference-buyer` and
      `arkhai-inference-domain` among the image's dependencies so the `market`
      binary loads every shipped plugin (market-composition delta scenario
      "Shipped domains are loaded", the installed half); `e2e-tests/settings.toml`
      gains `[default.inference]` (`registry_url`, `service_url`,
      `storefront_url`, `gateway_url`, the registry pins, the lane registries'
      pins, `seller_marketplace_credential`) and
      `e2e-tests/config/config-docker.yml` the lane's values, each a committed
      development value.
- [ ] 11.3 `e2e-tests/tests/e2e/roles/scenarios/inference/{__init__,conftest}.py`:
      `lane_setting` failing, never skipping, on an absent value
      (test-compatibility delta scenario "A lane setting is missing"); a
      profiled buyer from `create_profiled_buyer_cli` with the compute,
      API-credits, and inference registries all pinned (D11).
- [ ] 11.4 `test_inference_deal_buyer_cli.py` under
      `e2e-tests/tests/e2e/roles/scenarios/inference/`, marked
      `e2e_inference_deal`, over `DomainDealState`, `ordered_events`,
      and `assert_market_run_succeeded`, with the inference parts its own:
      (a) `market inference listing list` with a `model_id` filter and the
      three registries configured observes only the inference registry
      queried and only that model's listings (test-compatibility delta
      scenario "The buyer's schema filter is exercised"); (b) `market inference
      buy` of a small quantity into a new key, completing discovery,
      negotiation, and settlement on the development chain, the delivery
      events carrying the key, the gateway base URL, and the served model name;
      (c) the public result's `materialization` carries the listing's rate
      card and validates against the listing it carries; (d) `POST
      /v1/chat/completions` with the key and the served model answers `200`
      with the stub's exact text; (e) a request naming an unlisted model is
      `404`, and the key's remaining requests then succeed in full, which is
      the uncharged proof; (f) a second listing for another served model,
      published through the storefront's seller publish route with the lane's
      seller credential, is bought onto a second key, and that key at the
      gateway is `403` with `key_out_of_scope` and its balance intact, shown
      by a later top-up and the second gateway not existing (the scenario
      reads the authority's balance through no private route; the proof is
      the first key's request count); (g) the first key is consumed to `402`
      whose body carries the storefront and registry; (h) `market inference buy
      --key-id` tops it up and a request is admitted within the polling window
      after the three-second verification TTL (review 01 F2; inference delta
      scenario "A buyer tops up"); (i) a `stream: true` request yields
      server-sent events whose first arrives before the last (inference delta
      scenarios "A key bought for another model is presented", "A request
      names an unlisted model", "A key is exhausted", "A completion is
      streamed"; test-compatibility delta scenario "The lane runs").
- [ ] 11.5 `e2e-tests/tests/unit/test_domain_deal_helper.py` or a sibling: the
      inference scenario's stage order is produced and consumed through
      `require_state` with one producer per field, on the compute lanes'
      pattern (test-compatibility requirement "Exact e2e state dependencies").
- [ ] 11.6 Run `make -C e2e-tests test-e2e-inference` locally and record the
      run in the section note; run `make -C e2e-tests test-e2e-apicredits`
      once as well, since sections 1–3 touched the family the API-credits
      lane exercises, and record `e2e_credits_deal` and
      `e2e_credits_service_rollback` green (test-compatibility requirement "A
      deployable domain's deal runs on every end-to-end run"). A host that
      cannot run the lanes records that as the blocker it is, naming the
      cause, for closeout part 8.
- [ ] 11.7 **Verification.** `make test-e2e-unit` (the harness's unit level)
      and `make test-release-tooling`; the system level is `make -C e2e-tests
      test-e2e-inference` (`e2e_inference_deal`) and `test-e2e-apicredits`
      (`e2e_credits_deal`, `e2e_credits_service_rollback`). `make test`. The
      e2e image's dependencies change: `make lock PROJECTS=e2e-tests` and
      `make check-packaging`.

## 12. Closeout

The eleven parts of `openspec/README.md`'s "Plan closeout requirements", in
order, each specific to this change; closeout edits documentation only, and a
part that would need a code edit returns the change to implementation.

- [ ] 12.1 **Comment hygiene.** Confirm: `make check-comment-hygiene` passes,
      and the three recovered modules (5.3, 5.5, 5.6) and every new root were
      read for references to the withdrawn branch, the API-credits history, or
      this change. Anything found returns the change to implementation.
- [ ] 12.2 **Import placement.** Confirm: no function-level import this
      change added — in the family's vocabulary, contracts, authority, gate,
      and gateway, or in the four roles — lacks a verified circular-import or
      lazy-load reason. One that should move returns the change to
      implementation.
- [ ] 12.3 **Documentation compliance.** Re-check every decision in the
      promotion record below against `openspec/README.md`'s placement rules:
      normative behaviour in the owning `spec.md` (written by the archive from
      the five deltas), rationale and limits in the companions, repository-wide
      topology in `docs/development/ARCHITECTURE.md`, deployment conventions in
      `DEPLOYMENT_AND_CONFIG.md`; confirm no permanent document announces
      completion or names this change.
- [ ] 12.4 **Narrative compression.** Shorten each section's completed-task
      notes to final behaviour, material validation evidence, unresolved or
      deferred work, and destinations; move any alternative or debugging
      narrative they hold into `design.md` first.
- [ ] 12.5 **Roadmap currency.** `docs/development/ROADMAP.md`, Goal 8: the
      current-state prose now says the four roles exist and complete one deal
      at a flat charge per request, and the gap table's "No inference roles"
      row is removed, leaving metering, packaging, and qualification; name the
      update in the promotion record.
- [ ] 12.6 **Campaign index currency.** `openspec/changes/README.md`: this
      change's row and the Goal 8 campaign graph; every link resolves; `make
      check-change-index` passes. Other rows' `Depends on` are left as they
      are: `meter-inference-usage` and `package-inference-seller` are released
      at archive cleanup, not here.
- [ ] 12.7 **Packaging.** `make check-packaging` passes with every new
      project's lock current; `make check-architecture-change
      CHANGE=compose-inference-domain-stack` reports no exception or override
      row owned by this change.
- [ ] 12.8 **End-to-end pipeline.** Record the pipeline run — the `e2e-inference`
      job (`e2e_inference_deal`) and the `e2e-apicredits` job
      (`e2e_credits_deal`, `e2e_credits_service_rollback`, the family's
      unchanged bytes and the authority's upgrade-and-rollback path) — its
      result, and the scenarios that exercise this change. If it cannot run
      for a cause unrelated to the change, record the blocker naming the cause
      and the change that owns it, and treat the validations it gates as
      unrun.
- [ ] 12.9 **Promotion.** Write the permanent documents the record below
      names, file and heading exactly: the `inference` capability's
      `architecture.md` ("Role composition over the family kit",
      "Verification seams", "Current limits"); the `api-family` capability's
      `architecture.md` ("Contribution bundles" — the table gains an inference
      column; "The gate" — the separable verify step; a new section "The
      gateway"; "Current limits" — the `grant_terms` posture, and the sentence
      "Only API credits composes the kit" removed); `docs/development/ARCHITECTURE.md`
      ("Runtime service map" — the gateway role and the inference seller stack;
      "Local development" under "Deployment topology" — the third registry
      schema and the inference roles); `docs/development/DEPLOYMENT_AND_CONFIG.md`
      ("Per-domain stack composition" — the inference files, overlays, and the
      `vllm` profile; "Migrations at startup" — the `grant_terms` step and the
      previous image's rollback); `dev-env/identities/README.md` (a new
      section "The inference lane" and its rows in the stack table); then
      complete the design-promotion record last. No new capability companion
      is created, so `openspec/specs/README.md` gains no row; confirm its
      `inference` row, written by `add-inference-domain-contract`'s closeout,
      resolves.
- [ ] 12.10 **Documentation citations.** `make check-doc-citations
      CHANGE=compose-inference-domain-stack` after promotion, every match
      resolved; then `openspec validate compose-inference-domain-stack
      --strict` as the last check before the archive.
- [ ] 12.11 **Archival.** `openspec archive compose-inference-domain-stack
      -y`, merging the five deltas into `openspec/specs/{api-family,inference,
      deployment-state,test-compatibility,market-composition}/spec.md` and
      moving the change under `changes/archive/`; the index row then links the
      archive. Dependents are released at archive cleanup, not here.

## Design promotion record

| Accepted decision | Permanent location |
|---|---|
| D1 — the issuance projection names the served model and delivers the gateway URL | the `inference` capability's `spec.md` — "The issuance projection names the served model and pins the accepted terms"; the `api-family` capability's `architecture.md` — "Contribution bundles" (inference column) |
| D2 — the gateway is a family library composed by a domain executable | the `api-family` capability's `spec.md` — "A gateway in front of a model server is one family library"; its `architecture.md` — "The gateway"; `docs/development/ARCHITECTURE.md` — "Runtime service map" |
| D3 — the public result carries the contract's materialization, built from the extension's inputs; the selling library hands the extension a delivery context | the `inference` capability's `spec.md` — "The delivery's public result carries the accepted card"; its `architecture.md` — "Role composition over the family kit"; the `api-family` capability's `spec.md` — "The public-result extension receives the delivery's settlement context" |
| D4 — retries are charged as the kit charges them; the metering seam | the `inference` capability's `architecture.md` — "Current limits" |
| D5 — the stub model server is a test image; the `vllm` profile | `docs/development/DEPLOYMENT_AND_CONFIG.md` — "Per-domain stack composition"; the `deployment-state` capability's `spec.md` — "Local inference stack composition" |
| D6 — contribution values follow API credits' pattern | the `inference` capability's `spec.md` — "Inference roles are composed from independent distributions", "Issuance identifiers are inference-labelled and agree across the boundary"; the `api-family` capability's `architecture.md` — "Contribution bundles" (inference column) |
| D7 — the publish request carries the model card | the `inference` capability's `spec.md` — "Quota-backed publication" |
| D8 — the request-priced guard is one removable entry | the `inference` capability's `spec.md` — "Only request-priced rate cards are publishable without metered consumption" |
| D9 — Alkahest only, refused at startup | the `inference` capability's `spec.md` — "Alkahest is the only inference settlement mechanism" |
| D10 — Compose files, identities, and env targets mirror API credits | the `deployment-state` capability's `spec.md` — "Local inference stack composition"; `docs/development/DEPLOYMENT_AND_CONFIG.md` — "Per-domain stack composition"; `dev-env/identities/README.md` — "The inference lane" |
| D11 — the scenario runs in its own lane | the `test-compatibility` capability's `spec.md` — "Inference end-to-end deal path" |
| D12 — the buyer plugin's contributions | the `inference` capability's `spec.md` — "The buyer plugin discovers by model card under the inference schema"; the `api-family` capability's `architecture.md` — "Contribution bundles" (inference column) |
| D13 — the withdrawn modules are recovered, not rewritten | `design.md` only; the resulting behaviour promotes under D3, D7, and D8 |
| D14 — the gateway signs as the service role | the `inference` capability's `architecture.md` — "Role composition over the family kit" |
| D15 — the authority's database starts on the family chain | the `api-family` capability's `architecture.md` — "Current limits" (the existing migration-chain bullet, now true of a second domain) |
| D16 — verification seams and the measurable image | the `inference` capability's `spec.md` — "The gateway and buyer carry verification seams for a later proof"; its `architecture.md` — "Verification seams"; the `api-family` capability's `architecture.md` — "The gateway" |
| D17 — the three-party constraint on settlement composition | the `inference` capability's `spec.md` — "Alkahest is the only inference settlement mechanism" (the unmodified obligation list); its `architecture.md` — "Current limits" |
| D18 — implementation cadence | `design.md` only; the section order above is its record |
| review 01 F4 (with review 02 F1) — a key is scoped to its first grant's service, resource, and accepted terms | the `api-family` capability's `spec.md` — "A key is scoped to its first grant" |
| review 01 F1 (amended by review 02 F1) — the issuance subject carries the accepted terms, digest, and charge; the gateway charges the key's verified charge | the `inference` capability's `spec.md` — "The issuance projection names the served model and pins the accepted terms", "The gateway admits only paid requests for listed models"; the `api-family` capability's `spec.md` — "The issuance subject may carry accepted terms"; its `architecture.md` — "Contribution bundles" (inference column) |
| review 01 F3 — verification precedes the charge; the gate's separable verify step | the `api-family` capability's `spec.md` — "The gate verifies and charges in separable steps"; its `architecture.md` — "The gate" |
| review 02 F2 (with review 03 F2 and review 04 F3) — the proof hook binds to the accepted attestation through the terms digest | the `inference` capability's `architecture.md` — "Verification seams" |
| review 02 F3 — the family gateway consumes a domain-neutral offering the domain executable projects | the `api-family` capability's `spec.md` — "A gateway in front of a model server is one family library"; its `architecture.md` — "The gateway" |
| review 03 F1 — a key is enforced against the gateway's offering scope at verify and consume | the `api-family` capability's `spec.md` — "A key is scoped to its first grant" |
| review 03 F3 (amended by review 04 F1 and F2) — accepted terms persist as payload, digest, and charge in `grant_terms`, omitted from the wire when unset, rollback-safe | the `api-family` capability's `spec.md` — "The issuance subject may carry accepted terms"; its `architecture.md` — "Current limits"; `docs/development/DEPLOYMENT_AND_CONFIG.md` — "Migrations at startup" |
| plan review 06 F1 — the gateway discovers the listing it fronts by resource and served model, retrying until published | the `inference` capability's `spec.md` — "The gateway admits only paid requests for listed models"; its `architecture.md` — "Role composition over the family kit" |
| plan review 06 F3 — the request charge is positive and ledger-bounded | the `inference` capability's `spec.md` — "Only request-priced rate cards are publishable without metered consumption"; the `api-family` capability's `spec.md` — "The issuance subject may carry accepted terms" |
| review 01 F2 — a top-up is admitted after the gate's verification TTL | the `inference` capability's `spec.md` — "The gateway admits only paid requests for listed models"; its `architecture.md` — "Current limits" |
| Roadmap and index currency (closeout parts 5 and 6) | `docs/development/ROADMAP.md` — Goal 8 current state and gap table; `openspec/changes/README.md` — this change's row and the Goal 8 campaign graph |
