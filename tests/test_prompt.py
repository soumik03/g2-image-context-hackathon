from pathlib import Path

from adgen.prompt import PROMPT_TEMPLATE, build_prompt
from adgen.spec import GenerationSpec


def make_spec(**overrides):
    values = dict(
        id="prod-01",
        product_image=Path("unused.png"),
        geography="Tokyo, Japan",
        season="Winter",
        required_text="Step Into Winter",
    )
    values.update(overrides)
    return GenerationSpec(**values)


def test_prompt_is_exact_template_fill():
    prompt = build_prompt(make_spec())
    expected = PROMPT_TEMPLATE.replace("{geography}", "Tokyo, Japan") \
        .replace("{season}", "Winter") \
        .replace("{required_text}", "Step Into Winter")
    assert prompt == expected


def test_prompt_contains_fields_and_quoted_text():
    prompt = build_prompt(make_spec())
    assert "- Target geography: Tokyo, Japan\n" in prompt
    assert "- Season: Winter\n" in prompt
    assert '"Step Into Winter"' in prompt


def test_prompt_states_core_rules():
    prompt = build_prompt(make_spec())
    assert "source of truth" in prompt
    assert "Preserve its identity, shape, proportions, materials, colors" in prompt
    assert "Do not redesign, replace" in prompt
    assert "exactly as written" in prompt
    assert "Do not add any other text, slogans, prices, claims" in prompt
    assert "professional display advertisement" in prompt


def test_prompt_uses_only_the_three_text_fields():
    # The spec id and image path must never leak into the prompt.
    prompt = build_prompt(make_spec(id="secret-internal-id", product_image=Path("hidden_name.png")))
    assert "secret-internal-id" not in prompt
    assert "hidden_name" not in prompt


def test_braces_in_values_are_inserted_literally():
    prompt = build_prompt(make_spec(required_text="Save {20}% now"))
    assert '"Save {20}% now"' in prompt


def test_prompt_is_deterministic():
    assert build_prompt(make_spec()) == build_prompt(make_spec())
