"""Model identifier derivation."""

from __future__ import annotations

import pytest

from domains.inference.listings.identity import (
    derive_model_id,
    model_id_from_artifact_ref,
)

_CANONICAL = "meta-llama/llama-3.1-8b-instruct"


def test_derivation_lowercases_owner_and_name():
    assert derive_model_id("Meta-Llama", "Llama-3.1-8B-Instruct") == _CANONICAL


@pytest.mark.parametrize(
    "name",
    [
        "Llama-3.1-8B-Instruct-FP8",
        "Llama-3.1-8B-Instruct-AWQ",
        "Llama-3.1-8B-Instruct-GPTQ",
        "Llama-3.1-8B-Instruct-int4",
        "Llama-3.1-8B-Instruct-awq-int4",
    ],
)
def test_quantization_suffixes_are_stripped(name):
    assert derive_model_id("meta-llama", name) == _CANONICAL


@pytest.mark.parametrize(
    "ref",
    [
        "hf://meta-llama/Llama-3.1-8B-Instruct@0e9e39f",
        "https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct/tree/main",
        "meta-llama/Llama-3.1-8B-Instruct#main",
        "meta-llama/Llama-3.1-8B-Instruct:main",
        "hf://meta-llama/Llama-3.1-8B-Instruct-FP8@abc",
    ],
)
def test_independent_references_to_the_same_weights_converge(ref):
    assert model_id_from_artifact_ref(ref) == _CANONICAL


def test_private_weights_use_the_owners_namespace():
    assert derive_model_id("acme-research", "Atlas-7B") == "acme-research/atlas-7b"


def test_fine_tune_uses_the_fine_tuners_namespace():
    assert derive_model_id("acme-research", "Llama-3.1-8B-Legal") != _CANONICAL


@pytest.mark.parametrize("owner,name", [("", "x"), ("meta llama", "x"), ("meta/llama", "x"), ("meta", "-fp8")])
def test_segments_must_be_single_names(owner, name):
    with pytest.raises(ValueError):
        derive_model_id(owner, name)


def test_reference_without_owner_is_rejected():
    with pytest.raises(ValueError):
        model_id_from_artifact_ref("hf://llama-only")
