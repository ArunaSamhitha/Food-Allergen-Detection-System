import pytest

from allergencheck import Profile, analyze

ALL_DIETS = Profile(avoid=["peanut", "tree_nut", "shellfish", "gluten", "milk", "red_meat"])


def verdict(text, *avoid, custom=()):
    return analyze(text, Profile(list(avoid), list(custom)))


@pytest.mark.parametrize("text, avoid, expected", [
    ("Ingredients: roasted peanuts, salt.", ["peanut"], "unsafe"),
    ("Ingredients: sugar, whey protein, cocoa.", ["milk"], "unsafe"),
    ("Ingredients: semolina, water, salt.", ["gluten"], "unsafe"),
    ("Ingredients: rice, water, salt. Contains: soy.", ["soy"], "unsafe"),
    ("Ingredients: oats, sugar. May contain traces of almonds.", ["tree_nut"], "caution"),
    ("Ingredients: oats, sugar. Processed in a facility that also processes peanuts.", ["peanut"], "caution"),
    ("Ingredients: rice, water, sea salt, olive oil.", ["peanut", "milk", "gluten"], "safe"),
    ("", ["peanut"], "unreadable"),
])
def test_basic_verdicts(text, avoid, expected):
    assert verdict(text, *avoid).verdict == expected


@pytest.mark.parametrize("text, avoid", [
    ("Ingredients: cocoa butter, sugar, coconut milk.", ["milk"]),
    ("Ingredients: butternut squash, nutmeg, water chestnuts, coconut.", ["tree_nut"]),
    ("Ingredients: buckwheat flour, water. Gluten-free.", ["gluten", "wheat"]),
    ("Ingredients: eggplant, tomato, basil.", ["egg"]),
    ("Ingredients: oat milk, almond butter.", ["milk"]),
    ("Ingredients: peanut butter, jelly.", ["tree_nut"]),
    ("Ingredients: cream of tartar, flour.", ["milk"]),
    ("Peanut-free and dairy-free facility. Ingredients: rice, sugar.", ["peanut", "milk"]),
])
def test_look_alikes_are_not_flagged(text, avoid):
    report = verdict(text, *avoid)
    assert report.verdict == "safe", report.findings


def test_ocr_noise_still_caught():
    report = verdict("INGREDIENTS: SUGAR, PEANUTS0IL, ALMOMDS, SALT", "tree_nut")
    assert report.verdict == "unsafe"
    assert any(f.ocr_corrected for f in report.findings)


def test_ocr_digit_inside_word_is_repaired():
    assert verdict("Ingredients: wheat flour, mi1k, eggs", "milk").verdict == "unsafe"


def test_evidence_points_at_label_words():
    report = verdict("Ingredients: enriched flour (wheat flour, niacin), sugar, butter, eggs.", "milk", "gluten")
    found = {(f.category, f.term) for f in report.findings}
    assert ("milk", "butter") in found and ("gluten", "wheat") in found
    assert report.findings[0].source == "ingredients"
    gluten = [f.text for f in report.findings if f.category == "gluten"]
    assert gluten == ["enriched flour", "wheat flour"]  # one line per ingredient, not per word


def test_other_allergens_reported_even_if_not_avoided():
    report = verdict("Ingredients: flour, eggs, sesame seeds.", "peanut")
    assert report.verdict == "safe"
    assert set(report.other_allergens) >= {"Eggs", "Sesame", "Wheat"}


def test_real_words_are_not_spell_corrected():
    assert verdict("Ingredients: water, mustard seed, vinegar, button mushrooms.", "milk", "red_meat").verdict == "safe"


def test_plain_flour_means_wheat_but_rice_flour_does_not():
    assert verdict("Ingredients: flour, sugar.", "gluten").verdict == "unsafe"
    assert verdict("Ingredients: rice flour, sugar.", "gluten", "wheat").verdict == "safe"


def test_custom_words():
    assert verdict("Ingredients: kiwi, apple, sugar.", custom=["kiwi"]).verdict == "unsafe"


def test_ambiguous_ingredients_become_caution():
    report = verdict("Ingredients: water, sugar, natural flavors.", "peanut")
    assert report.verdict == "caution" and report.checks


def test_definite_beats_precaution_and_both_are_listed():
    report = verdict("Ingredients: milk chocolate (sugar, milk). May contain hazelnuts.", "milk", "tree_nut")
    assert report.verdict == "unsafe"
    sources = {(f.category, f.source) for f in report.findings}
    assert ("tree_nut", "precaution") in sources and ("milk", "ingredients") in sources


def test_realistic_label():
    label = """NUTRITION FACTS Serving size 2 cookies
    INGREDIENTS: UNBLEACHED ENRICHED FLOUR (WHEAT FLOUR, NIACIN, REDUCED IRON),
    SEMISWEET CHOCOLATE CHIPS (SUGAR, CHOCOLATE, COCOA BUTTER, SOY LECITHIN, VANILLA), BUTTER (CREAM),
    SUGAR, EGGS, BAKING SODA, SALT. CONTAINS: WHEAT, MILK, EGG, SOY.
    MANUFACTURED ON SHARED EQUIPMENT WITH PEANUTS AND TREE NUTS."""
    report = analyze(label, ALL_DIETS)
    assert report.verdict == "unsafe"
    labels = {f.label for f in report.findings if f.source != "precaution"}
    assert labels == {"Gluten", "Milk"}
    assert {f.label for f in report.findings if f.source == "precaution"} == {"Peanuts", "Tree nuts"}
    assert "Soy" in report.other_allergens


def test_unknown_category_rejected():
    with pytest.raises(ValueError):
        analyze("x", Profile(["kryptonite"]))
