"""Allergen and diet vocabulary.

Each category lists the words that indicate it on an ingredient label, plus
"exclude" phrases that look like a match but are not (e.g. "nutmeg" is not a
tree nut, "cocoa butter" is not dairy). Terms are matched as whole words or
phrases, case-insensitively.

The nine allergen categories follow the US FALCPA major food allergens
(milk, egg, fish, crustacean shellfish, tree nuts, peanuts, wheat, soybeans,
sesame). This list is a screening aid, not a medical guarantee.
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Category:
    key: str
    label: str
    kind: str  # "allergen" or "diet"
    terms: tuple[str, ...]
    exclude: tuple[str, ...] = field(default_factory=tuple)


# In the US, an unqualified "flour" on a label means wheat flour. These do not.
NON_WHEAT_FLOURS = tuple(f"{grain} flour" for grain in (
    "rice", "brown rice", "almond", "corn", "oat", "coconut", "chickpea", "buckwheat", "tapioca", "potato",
    "cassava", "sorghum", "millet", "quinoa", "soy", "soya", "teff", "amaranth", "banana", "arrowroot",
    "lentil", "pea", "hazelnut", "cashew", "peanut"))

CATEGORIES: dict[str, Category] = {c.key: c for c in [
    Category("peanut", "Peanuts", "allergen", (
        "peanut", "peanuts", "groundnut", "groundnuts", "arachis", "arachis oil", "monkey nuts",
        "beer nuts", "mandelonas",
    ), ("peanut-free", "peanut free", "no peanuts")),
    Category("tree_nut", "Tree nuts", "allergen", (
        "almond", "almonds", "walnut", "walnuts", "cashew", "cashews", "pecan", "pecans", "hazelnut",
        "hazelnuts", "filbert", "filberts", "pistachio", "pistachios", "macadamia", "brazil nut",
        "brazil nuts", "pine nut", "pine nuts", "pignoli", "praline", "marzipan", "nougat", "gianduja",
        "nut butter", "nut oil", "tree nut", "tree nuts", "nuts", "nut",
    ), ("nutmeg", "butternut", "nut-free", "nut free", "tree nut free", "doughnut", "donut", "chestnut",
        "water chestnut", "coconut", "nutritional", "nutrition", "nutrient", "nutrients", "no nuts",
        "peanut", "peanuts", "groundnut", "beer nuts", "monkey nuts")),
    Category("milk", "Milk", "allergen", (
        "milk", "milk powder", "milk solids", "skim milk", "whole milk", "butter", "buttermilk", "cream",
        "cheese", "whey", "whey protein", "casein", "caseinate", "sodium caseinate", "calcium caseinate",
        "lactose", "lactalbumin", "lactoglobulin", "ghee", "yogurt", "yoghurt", "curd", "curds", "kefir",
        "custard", "paneer", "dairy",
    ), ("cocoa butter", "shea butter", "peanut butter", "almond butter", "nut butter", "apple butter",
        "coconut milk", "coconut cream", "almond milk", "oat milk", "soy milk", "rice milk", "cashew milk",
        "cream of tartar", "milk-free", "milk free", "dairy-free", "dairy free", "non-dairy", "nondairy",
        "lactose-free", "lactose free", "milkweed", "butternut", "buttercup")),
    Category("egg", "Eggs", "allergen", (
        "egg", "eggs", "egg white", "egg yolk", "albumin", "albumen", "ovalbumin", "lysozyme", "mayonnaise",
        "meringue", "ovomucoid", "eggnog",
    ), ("eggplant", "egg plant", "egg-free", "egg free", "eggless")),
    Category("fish", "Fish", "allergen", (
        "fish", "anchovy", "anchovies", "cod", "salmon", "tuna", "tilapia", "pollock", "haddock", "sardine",
        "sardines", "mackerel", "trout", "halibut", "bass", "catfish", "fish sauce", "fish oil",
        "worcestershire sauce",
    ), ("fish-free", "fish free", "shellfish", "crayfish")),
    Category("shellfish", "Shellfish", "allergen", (
        "shellfish", "shrimp", "prawn", "prawns", "crab", "lobster", "crayfish", "crawfish", "langoustine",
        "krill", "scampi",
    ), ("shellfish-free", "shellfish free", "crab apple", "crabapple")),
    Category("wheat", "Wheat", "allergen", (
        "wheat", "wheat flour", "whole wheat", "durum", "semolina", "spelt", "farro", "einkorn", "emmer",
        "kamut", "bulgur", "couscous", "seitan", "farina", "graham flour", "wheat germ", "wheat starch",
        "flour", "enriched flour", "bleached flour", "unbleached flour", "all-purpose flour",
    ), ("buckwheat", "wheat-free", "wheat free") + NON_WHEAT_FLOURS),
    Category("soy", "Soy", "allergen", (
        "soy", "soya", "soybean", "soybeans", "soy lecithin", "soya lecithin", "tofu", "tempeh", "edamame",
        "miso", "natto", "soy sauce", "shoyu", "tamari", "textured vegetable protein", "tvp",
    ), ("soy-free", "soy free")),
    Category("sesame", "Sesame", "allergen", (
        "sesame", "sesame seed", "sesame seeds", "sesame oil", "tahini", "tahina", "benne", "gingelly",
        "halvah", "halva",
    ), ("sesame-free", "sesame free")),
    # Diets and intolerances
    Category("gluten", "Gluten", "diet", (
        "gluten", "wheat", "barley", "rye", "malt", "malt extract", "malt vinegar", "brewer's yeast",
        "triticale", "spelt", "durum", "semolina", "farro", "einkorn", "emmer", "kamut", "bulgur",
        "couscous", "seitan", "farina", "graham flour", "flour", "enriched flour",
    ), ("gluten-free", "gluten free", "buckwheat", "wheat-free", "wheat free") + NON_WHEAT_FLOURS),
    Category("red_meat", "Red meat", "diet", (
        "beef", "pork", "lamb", "mutton", "veal", "venison", "goat", "bacon", "ham", "prosciutto",
        "pepperoni", "salami", "lard", "tallow", "chorizo",
    ), ("beef-free", "pork-free", "hamburger bun")),
    Category("meat", "Meat (vegetarian)", "diet", (
        "beef", "pork", "lamb", "mutton", "veal", "venison", "goat", "bacon", "ham", "chicken", "turkey",
        "duck", "lard", "tallow", "gelatin", "gelatine", "anchovy", "anchovies", "fish", "shrimp",
        "chicken broth", "beef broth", "beef stock", "chicken stock", "rennet",
    ), ("meat-free", "meatless")),
]}

# Ingredients whose source is ambiguous: flagged as "check" rather than a match.
AMBIGUOUS: dict[str, tuple[str, str]] = {
    "natural flavors": ("any", "can hide many sources; check with the manufacturer"),
    "natural flavor": ("any", "can hide many sources; check with the manufacturer"),
    "spices": ("any", "spice blends occasionally contain allergens"),
    "lecithin": ("soy", "often from soy or egg"),
    "gelatin": ("red_meat", "often from pork or beef"),
    "gelatine": ("red_meat", "often from pork or beef"),
    "modified food starch": ("wheat", "may be from wheat; US labels must say so if it is"),
    "dextrin": ("gluten", "may be from wheat"),
    "hydrolyzed vegetable protein": ("soy", "often from soy or wheat"),
}

PRECAUTION_MARKERS = (
    "may contain", "may also contain", "may include", "traces of", "trace of", "made in a facility",
    "made on equipment", "produced in a facility", "processed in a facility", "manufactured in a facility",
    "processed on equipment", "produced on shared equipment", "shared equipment", "same facility",
    "processed in a plant",
)

CONTAINS_MARKERS = ("contains:", "contains ", "allergens:", "allergy advice:", "allergy information:")

# Real ingredient words that sit one typo away from an allergen term. The OCR
# spelling-correction pass takes these at face value instead of "correcting" them.
KNOWN_WORDS = frozenset("""
batter bitter butler button buttons mustard lactase curls cards marina parley barely saloon smelt
sugar water salt flour starch vinegar honey yeast pepper garlic onion onions tomato tomatoes potato potatoes
celery carrot carrots spinach lemon orange apple apples grape raisin raisins vanilla cocoa chocolate cinnamon
ginger paprika turmeric oregano basil thyme parsley canola sunflower olive palm coconut citric malic lactic
ascorbic sodium potassium calcium phosphate sulfate niacin thiamine riboflavin folic glucose fructose dextrose
maltodextrin sorbitol xanthan pectin carrageenan beans lentils chickpeas quinoa maize tapioca cassava sorghum
millet peppers mushrooms seasoning flavor flavors flavour flavours color colour extract powder juice
concentrate natural artificial organic dried roasted toasted enriched bleached unbleached reduced modified
hydrogenated partially vegetable vegetables cultured salted unsalted sweetened unsweetened leavening baking
""".split())
