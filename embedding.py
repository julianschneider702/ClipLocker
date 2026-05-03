import re
import sqlite3
from typing import Any

import numpy as np
from sentence_transformers import CrossEncoder, SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM


CATEGORY_WEIGHTS = {
    "people": 2.0,
    "activity": 2.0,
    "place": 1.8,
    "object": 1.2,
    "emotion/state": 1.0,
    "time": 0.8,
    "weather": 0.8,
}

hint_words_exact = {
    "thus", "hence", "consequently", "meanwhile",
    "afterwards", "afterward", "nevertheless", "however",
    "therefore", "instead", "additionally",
}

hint_phrases = {
    "this is why", "that is why", "that's why",
    "because of this", "as a result", "for this reason",
    "in doing so", "by doing so", "which is why",
    "from that moment", "shortly after", "not long after",
    "despite this", "in spite of this",
    "at this place", "in this room", "in this place",
    "here it", "there it", "here was", "there was",
    "from there", "after that", "before that",
    "at the same time", "in the meantime", "These"
}

SIGNAL_MAP = {

    # ------------------------------------------------------------------ #
    # PEOPLE                                                               #
    # ------------------------------------------------------------------ #

    "peasants":         ["peasant"],
    "farmer":           ["peasant", "tilling", "field", "harvesting"],
    "farmers":          ["peasant", "tilling", "field", "crowd"],
    "monks":            ["monk"],
    "priest":           ["church"],
    "priests":          ["priest", "church"],
    "nuns":             ["nun"],
    "knights":          ["knight"],
    "squire":           ["knight", "sword-training", "child"],
    "squires":          ["squire", "knight", "sword-training", "child"],
    "nobleman":         ["noble-man"],
    "noblewoman":       ["noble-woman"],
    "noble":            ["noble-man", "noble-woman"],
    "nobles":           ["noble-man", "noble-woman"],
    "guards":           ["guard"],
    "soldier":          ["army", "knight", "fighting", "battlefield"],
    "soldiers":         ["army", "knight", "fighting", "battlefield"],
    "army":             ["marching", "battlefield", "fighting", "military-camp"],
    "mercenary":        ["knight"],
    "mercenaries":      ["mercenary", "knight"],
    "archers":          ["archer"],
    "merchant":         ["trading", "coins", "market"],
    "merchants":        ["merchant", "trading", "market", "coins"],
    "trader":           ["merchant", "trading", "market", "coins"],
    "traders":          ["merchant", "trading", "market", "coins"],
    "carpenters":       ["carpenter"],
    "scribe":           ["writing", "scroll", "book"],
    "scribes":          ["writing", "scroll", "book"],
    "baker":            ["baking"],
    "beggars":          ["beggar", "begging"],
    "thieves":          ["thief", "prison", "stealing"],
    "musicians":        ["musician"],
    "sailors":          ["sailor", "ship"],
    "healer":           ["treating-patient", "herbs", "potion"],
    "children":         ["child"],
    "people":           ["crowd", "village", "market"],
    "woman":            ["family", "peasant", "noble-woman"],
    "women":            ["family", "peasant", "noble-woman"],
    "men":              ["crowd", "noble-man"],

    "bakers":           ["baker"],
    "blacksmiths":      ["blacksmith"],
    "innkeepers":       ["innkeeper"],
    "millers":          ["miller"],
    "lumberjacks":      ["lumberjack"],
    "alchemists":       ["alchemist"],
    "doctors":          ["doctor"],
    "healers":          ["doctor"],
    "jesters":          ["jester"],

    "kings":            ["king"],
    "cooks":            ["cooking", "kitchen"],

    # ------------------------------------------------------------------ #
    # ACTIVITY                                                             #
    # ------------------------------------------------------------------ #

    "walk":             ["walking"],
    "run":              ["running", "road"],
    "sleep":            ["sleeping"],
    "carried":          ["carrying"],
    "pray":             ["praying", "church", "monk"],
    "praying":          ["church", "monk", "priest", "interior"],
    "prayer":           ["praying", "church", "monk"],
    "worship":          ["praying", "church", "interior"],
    "kneel":            ["praying", "church"],
    "kneeling":         ["praying", "church"],
    "fight":            ["fighting", "battlefield", "sword"],
    "fighting":         ["battlefield", "sword", "army"],
    "combat":           ["fighting", "battlefield", "army"],
    "battle":           ["fighting", "battlefield", "army", "castle"],
    "hunt":             ["hunting", "forest", "bow", "archer"],
    "hunting":          ["forest", "bow", "archer", "bear"],
    "cook":             ["cooking", "kitchen", "fire"],
    "cooking":          ["kitchen", "fire", "kettle", "indoor-fireplace"],
    "bake":             ["baking-oven", "bread", "cooking", "kitchen"],
    "baking":           ["baking-oven", "bread", "dough", "kitchen"],
    "eat":              ["eating", "table", "food-container"],
    "eating":           ["table", "banquet", "tavern"],
    "feast":            ["eating", "drinking", "banquet", "crowd"],
    "drink":            ["drinking", "tavern", "beer"],
    "drinking":         ["tavern", "beer", "wine", "interior"],
    "pour":             ["pouring-a-drink", "jug", "tavern"],
    "pouring":          ["pouring-a-drink", "jug", "tavern"],
    "build":            ["building", "construction-site", "saw", "hammer"],
    "building":         ["construction-site", "saw", "hammer"],
    "construct":        ["building", "construction-site"],
    "write":            ["writing", "scroll", "book", "interior"],
    "writing":          ["scroll", "book", "candle", "interior"],
    "read":             ["reading", "book", "scroll", "interior"],
    "reading":          ["book", "scroll", "library", "interior"],
    "ride":             ["horse-riding", "horse", "road"],
    "riding":           ["horse", "road", "knight"],
    "march":            ["marching", "army", "battlefield"],
    "marching":         ["army", "battlefield", "road"],
    "till":             ["tilling", "field", "plow", "peasant"],
    "tilling":          ["field", "plow", "peasant", "harvesting"],
    "plowing":          ["tilling", "field", "plow"],
    "ploughing":        ["tilling", "field", "plow"],
    "harvest":          ["harvesting", "field", "grain", "scythe"],
    "harvesting":       ["field", "grain", "scythe", "peasant"],
    "sow":              ["tilling", "field", "peasant"],
    "sowing":           ["tilling", "field", "grain"],
    "plant":            ["tilling", "field", "vegetable"],
    "planting":         ["tilling", "field", "vegetable", "peasant"],
    "grow":             ["field", "vegetable", "harvesting"],
    "growing":          ["field", "vegetable", "grain"],
    "grew":             ["field", "vegetable", "harvesting", "peasant"],
    "dig":              ["tilling", "field", "peasant"],
    "digging":          ["tilling", "field", "construction-site"],
    "smith":            ["smithing", "blacksmith", "anvil", "fire"],
    "smithing":         ["blacksmith", "anvil", "fire", "workshop"],
    "forge":            ["smithing", "blacksmith", "anvil", "fire"],
    "forging":          ["smithing", "blacksmith", "fire", "workshop"],
    "trade":            ["trading", "merchant", "coins", "market"],
    "trading":          ["merchant", "coins", "market"],
    "sell":             ["trading", "merchant", "market"],
    "selling":          ["trading", "merchant", "market"],
    "buy":              ["trading", "merchant", "coins"],
    "buying":           ["trading", "coins", "market"],
    "gamble":           ["gambling", "tavern", "coins"],
    "gambling":         ["tavern", "coins", "interior"],
    "beg":              ["begging", "beggar"],
    "begging":          ["beggar"],
    "arrest":           ["arresting", "guard", "prison"],
    "arresting":        ["guard", "prison", "dungeon"],
    "train":            ["sword-training", "exercising", "knight"],
    "training":         ["sword-training", "exercising", "squire"],
    "spar":             ["sword-training", "sword", "knight"],
    "sparring":         ["sword-training", "sword", "yard"],
    "exercise":         ["exercising", "yard", "sword-training"],
    "exercising":       ["yard", "sword-training"],
    "stitch":           ["stitching", "needle", "interior"],
    "stitching":        ["needle", "interior", "cottage"],
    "sew":              ["stitching", "needle"],
    "sewing":           ["stitching", "needle", "interior"],
    "chop":             ["chopping", "axe", "firewood"],
    "chopping":         ["axe", "firewood", "lumberjack"],
    "saw":              ["sawing", "building"],
    "sawing":           ["building", "construction-site"],
    "chisel":           ["chiseling", "building", "stone"],
    "chiseling":        ["building", "construction-site", "stone"],
    "gather":           ["gathering-herbs", "herbs", "forest"],
    "gathering":        ["gathering-herbs", "herbs", "forest"],
    "sharpen":          ["sharpening-a-tool", "knife", "sword"],
    "sharpening":       ["sharpening-a-tool", "knife", "workshop"],
    "treat":            ["treating-patient", "herbs", "bed"],
    "treating":         ["treating-patient", "bed", "herbs"],
    "heal":             ["treating-patient", "herbs", "potion"],
    "healing":          ["treating-patient", "herbs", "potion"],
    "count":            ["money-counting", "coins", "merchant"],
    "counting":         ["money-counting", "coins", "market"],
    "siege":            ["army", "battlefield", "castle"],
    "jousting":         ["tournament", "knight", "horse"],
    "joust":            ["tournament", "knight", "horse"],
    "execute":          ["gallows", "dead", "crowd"],
    "execution":        ["gallows", "dead", "crowd"],
    "bury":             ["burial", "graveyard", "dead"],
    "burying":          ["burial", "graveyard"],
    "smoking":          ["smokehouse", "smoke", "raw-meat"],
    "cure":             ["smokehouse", "raw-meat", "smoke"],

    "walked":           ["walking"],
    "ran":              ["running"],
    "rode":             ["horse-riding"],
    "fought":           ["fighting"],
    "built":            ["building"],
    "dug":              ["tilling"],
    "sat":              ["sitting"],
    "stood":            ["standing"],
    "slept":            ["sleeping"],
    "hunted":           ["hunting"],
    "cooked":           ["cooking"],
    "prayed":           ["praying"],
    "marched":          ["marching"],
    "harvested":        ["harvesting"],
    "traded":           ["trading"],
    "sold":             ["trading"],
    "bought":           ["trading"],
    "wore":             ["clothes"],
    "ate":              ["eating"],
    "drank":            ["drinking"],
    "begged":           ["beggar", "begging"],

    "hunter":           ["hunting", "forest", "bow", "bear"],
    "hunters":          ["hunter", "hunting", "forest", "crowd"],
    "fighter":          ["fighting", "sword", "battlefield", "armor"],
    "fighters":         ["fighter", "fighting", "battlefield", "crowd"],
    "rider":            ["horse-riding", "horse", "road", "saddle"],
    "riders":           ["rider", "horse-riding", "horse", "crowd"],
    "builder":          ["building", "construction-site", "hammer", "saw"],
    "builders":         ["builder", "building", "construction-site", "crowd"],
    "grower":           ["field", "vegetable", "harvesting", "peasant"],
    "growers":          ["grower", "field", "harvesting", "crowd"],
    "digger":           ["tilling", "field", "construction-site", "tool-collection"],
    "diggers":          ["digger", "tilling", "field", "crowd"],
    "worshipper":       ["praying", "church", "interior", "cross"],
    "worshippers":      ["worshipper", "praying", "church", "crowd"],

    "canteen":          ["food-container", "carrying", "road"],
    "flask":            ["potion", "food-container", "carrying"],
    "pitcher":          ["jug", "pouring-a-drink", "tavern"],
    "goblet":           ["wine", "banquet", "table"],
    "tankard":          ["beer", "tavern", "table"],
    "cloak":            ["clothes", "travel", "road"],
    "tunic":            ["clothes", "peasant", "interior"],
    "hood":             ["clothes", "cloak", "nighttime"],
    "boots":            ["clothes", "walking", "road"],
    "gloves":           ["clothes", "smithing", "workshop"],
    "rope":             ["carrying", "yard", "well"],
    "chain":            ["prison", "dungeon", "arresting"],
    "cage":             ["prison", "dungeon", "guard"],
    "torch-holder":     ["torch", "corridor", "castle", "interior"],
    "brazier":          ["fire", "interior", "castle"],
    "trough":           ["barn", "pig", "cow"],
    "saddle":           ["horse", "horse-riding", "road"],
    "reins":            ["horse", "horse-riding", "carrying"],
    "quiver":           ["arrow", "bow", "archer", "hunting"],

    # ------------------------------------------------------------------ #
    # PLACE                                                                #
    # ------------------------------------------------------------------ #

    "church":           ["interior", "praying", "candle", "cross"],
    "chapel":           ["church", "interior", "praying"],
    "cathedral":        ["church", "interior", "cross"],
    "castle":           ["interior", "wall", "gate", "guard"],
    "fortress":         ["castle", "wall", "gate"],
    "dungeon":          ["interior", "prison", "torch"],
    "prison":           ["interior", "dungeon", "guard"],
    "tavern":           ["interior", "drinking", "beer", "innkeeper"],
    "inn":              ["tavern", "innkeeper", "interior", "beer"],
    "market":           ["trading", "crowd", "merchant", "coins"],
    "marketplace":      ["market", "trading", "crowd"],
    "village":          ["peasant", "cottage", "road"],
    "town":             ["village", "market", "crowd"],
    "city":             ["crowd", "market"],
    "forest":           ["hunting", "lumberjack", "bow", "bear"],
    "woods":            ["forest", "hunting", "lumberjack"],
    "field":            ["tilling", "harvesting", "peasant", "grain"],
    "fields":           ["tilling", "harvesting", "peasant", "grain"],
    "barn":             ["interior", "grain", "livestock"],
    "kitchen":          ["interior", "cooking", "baking-oven", "fire"],
    "corridor":         ["interior", "castle", "torch"],
    "hallway":          ["corridor", "interior", "castle"],
    "stairs":           ["interior", "castle"],
    "yard":             ["castle", "village", "well"],
    "courtyard":        ["yard", "castle", "guard"],
    "throne":           ["throne-room", "castle", "king", "crown"],
    "battlefield":      ["fighting", "army", "dead", "sword"],
    "camp":             ["military-camp", "tent", "army", "fire"],
    "river":            ["bridge", "ship"],
    "stream":           ["river", "bridge"],
    "lake":             ["ship", "sailor"],
    "pond":             ["lake"],
    "bridge":           ["river", "road", "journey"],
    "road":             ["walking", "carriage", "horse", "journey"],
    "path":             ["road", "walking", "forest"],
    "graveyard":        ["burial", "dead", "cross"],
    "cemetery":         ["graveyard", "burial", "dead"],
    "ruin":             ["castle", "stone", "wall"],
    "ruins":            ["ruin", "stone", "wall"],
    "workshop":         ["smithing", "anvil", "hammer", "interior"],
    "library":          ["interior", "book", "scroll", "reading"],
    "cottage":          ["interior", "family", "village"],
    "hut":              ["cottage", "interior", "peasant"],
    "tent":             ["military-camp", "army", "fire"],
    "tents":            ["tent", "military-camp", "army"],
    "construction":     ["building", "saw", "hammer"],
    "tournament":       ["knight", "horse", "crowd"],
    "wedding":          ["crowd", "church", "banquet"],
    "burial":           ["graveyard", "dead", "cross"],
    "grave":            ["graveyard", "burial", "dead"],
    "tomb":             ["burial", "graveyard", "stone"],
    "banquet":          ["eating", "drinking", "crowd", "noble-man"],
    "smokehouse":       ["smoke", "raw-meat", "fire"],
    "mill":             ["grain", "miller", "water-wheel"],

    # ------------------------------------------------------------------ #
    # OBJECTS                                                              #
    # ------------------------------------------------------------------ #

    "sword":            ["knight", "soldier", "mercenary", "guard", "fighting"],
    "swords":           ["sword", "knight", "fighting", "crowd"],
    "axe":              ["lumberjack", "chopping", "firewood"],
    "axes":             ["axe", "lumberjack", "chopping"],
    "bow":              ["arrow", "archer", "hunting", "forest"],
    "longbow":          ["bow", "arrow", "archer", "hunting"],
    "arrow":            ["bow", "archer", "hunting"],
    "arrows":           ["arrow", "bow", "archer"],
    "crossbow":         ["archer", "guard", "hunting"],
    "spear":            ["guard", "soldier", "army", "fighting"],
    "spears":           ["spear", "guard", "army"],
    "shield":           ["soldier", "knight", "fighting", "army"],
    "shields":          ["shield", "soldier", "fighting"],
    "armor":            ["knight", "soldier", "guard", "fighting"],
    "armour":           ["armor", "knight", "soldier"],
    "helmet":           ["armor", "knight", "soldier", "guard"],
    "hammer":           ["blacksmith", "smithing", "anvil", "workshop"],
    "anvil":            ["blacksmith", "smithing", "workshop", "fire"],
    "knife":            ["cooking", "kitchen", "butcher"],
    "knives":           ["knife", "cooking", "kitchen"],
    "scythe":           ["harvesting", "field", "grain", "peasant"],
    "plow":             ["tilling", "field", "peasant", "cow"],
    "plough":           ["tilling", "field", "peasant", "cow"],
    "needle":           ["stitching", "interior", "clothes"],
    "cannon":           ["siege", "army", "gunpowder", "battlefield"],
    "gunpowder":        ["cannon", "siege", "army"],
    "gallows":          ["dead", "crowd", "prison"],
    "horseshoe":        ["blacksmith", "smithing", "horse"],
    "bread":            ["baking-oven", "baker", "kitchen", "eating"],
    "dough":            ["baking-oven", "baker", "kitchen"],
    "grain":            ["mill", "harvesting", "field", "barn"],
    "wheat":            ["grain", "field", "harvesting", "peasant"],
    "vegetable":        ["field", "kitchen", "peasant", "harvesting"],
    "vegetables":       ["vegetable", "field", "kitchen", "peasant"],
    "fruit":            ["fruits", "market", "eating"],
    "fruits":           ["market", "kitchen", "eating"],
    "meat":             ["raw-meat", "market", "cooking"],
    "fish":             ["raw-fish", "river", "cooking"],
    "soup":             ["kettle", "cooking", "kitchen", "fire"],
    "broth":            ["soup", "kettle", "cooking"],
    "stew":             ["soup", "kettle", "cooking", "kitchen"],
    "herbs":            ["gathering-herbs", "alchemist", "forest"],
    "herb":             ["herbs", "gathering-herbs", "forest"],
    "honey":            ["market", "kitchen"],
    "cheese":           ["market", "kitchen", "eating"],
    "egg":              ["chicken", "kitchen", "cooking"],
    "eggs":             ["egg", "chicken", "kitchen"],
    "spice":            ["spices", "market", "cooking"],
    "spices":           ["market", "trading", "cooking"],
    "salt":             ["market", "kitchen", "trading"],
    "beer":             ["tavern", "drinking", "innkeeper"],
    "ale":              ["beer", "tavern", "drinking"],
    "wine":             ["tavern", "drinking", "banquet"],
    "potion":           ["alchemist", "herbs", "workshop"],
    "candle":           ["church", "interior", "praying", "monk"],
    "candles":          ["candle", "church", "interior"],
    "torch":            ["castle", "dungeon", "corridor", "interior"],
    "torches":          ["torch", "castle", "interior"],
    "lantern":          ["nighttime", "road", "interior"],
    "fire":             ["indoor-fireplace", "outdoor-campfire", "cooking", "smithing"],
    "flames":           ["fire", "indoor-fireplace", "smithing"],
    "embers":           ["fire", "outdoor-campfire", "indoor-fireplace"],
    "firewood":         ["lumberjack", "chopping", "fire", "outdoor-campfire"],
    "campfire":         ["outdoor-campfire", "military-camp", "nighttime", "fire"],
    "hearth":           ["indoor-fireplace", "fire", "cooking", "cottage"],
    "fireplace":        ["indoor-fireplace", "fire", "cooking", "interior"],
    "oven":             ["baking-oven", "bread", "baker", "kitchen"],
    "kettle":           ["cooking", "fire", "kitchen", "indoor-fireplace"],
    "pot":              ["kettle", "cooking", "kitchen", "fire"],
    "jug":              ["tavern", "drinking", "pouring-a-drink"],
    "barrel":           ["tavern", "barn", "market", "beer"],
    "bucket":           ["well", "yard"],
    "food":             ["eating", "cooking", "market"],
    "meal":             ["eating", "banquet", "tavern"],
    "book":             ["reading", "library", "scroll"],
    "books":            ["book", "reading", "library"],
    "scroll":           ["writing", "library", "interior"],
    "scrolls":          ["scroll", "writing", "library"],
    "manuscript":       ["scroll", "book", "writing"],
    "letter":           ["writing", "interior"],
    "map":              ["journey", "road", "military-camp"],
    "compass":          ["journey", "map", "sailor"],
    "coins":            ["trading", "merchant", "market", "money-counting"],
    "coin":             ["coins", "trading", "merchant"],
    "gold":             ["coins", "trading", "noble-man"],
    "money":            ["coins", "trading", "market"],
    "crown":            ["king", "castle", "throne-room"],
    "bell":             ["church", "village", "interior"],
    "cross":            ["church", "praying", "graveyard"],
    "painting":         ["interior", "castle", "church"],
    "bed":              ["sleeping", "interior", "treating-patient"],
    "table":            ["interior", "eating", "tavern"],
    "well":             ["yard", "village", "bucket"],
    "gate":             ["castle", "guard", "wall"],
    "wall":             ["castle", "guard", "siege"],
    "walls":            ["wall", "castle", "guard"],
    "roof":             ["cottage", "barn", "building"],
    "window":           ["interior", "castle", "cottage"],
    "door":             ["interior", "cottage", "castle"],
    "drawbridge":       ["castle", "gate", "siege"],
    "tower":            ["castle", "wall", "guard"],
    "ship":             ["sailor", "river", "lake"],
    "boat":             ["ship", "river", "sailor"],
    "carriage":         ["road", "horse", "journey"],
    "cart":             ["road", "horse", "carrying"],
    "horse":            ["horse-riding", "knight", "road"],
    "horses":           ["horse", "horse-riding", "knight"],
    "ox":               ["tilling", "plow", "field"],
    "oxen":             ["ox", "tilling", "field"],
    "cow":              ["barn", "field", "village"],
    "cattle":           ["cow", "barn", "field"],
    "sheep":            ["barn", "field", "village"],
    "pig":              ["barn", "village", "market"],
    "pigs":             ["pig", "barn", "village"],
    "chicken":          ["barn", "village", "egg"],
    "hen":              ["chicken", "barn", "egg"],
    "dog":              ["hunting", "village", "cottage"],
    "dogs":             ["dog", "hunting", "village"],
    "cat":              ["cottage", "interior", "village"],
    "bear":             ["hunting", "forest", "fighting"],
    "bird":             ["forest", "field", "daytime"],
    "birds":            ["bird", "forest", "field"],
    "rat":              ["dungeon", "barn", "interior"],
    "rats":             ["rat", "dungeon", "barn"],
    "insect":           ["field", "forest", "daytime"],
    "water-wheel":      ["mill", "miller", "grain", "river"],
    "windmill":         ["mill", "miller", "grain"],
    "tool":             ["tool-collection", "workshop", "blacksmith"],
    "tools":            ["tool-collection", "workshop"],
    "clothes":          ["stitching", "needle", "market"],
    "straw":            ["barn", "interior", "field"],
    "timber":           ["building", "construction-site", "lumberjack"],
    "wood":             ["firewood", "lumberjack", "building"],
    #"stone":            ["castle", "church", "construction-site", "ruin"],
    "iron":             ["blacksmith", "smithing", "anvil", "workshop"],
    "steel":            ["blacksmith", "smithing", "sword"],
    "smoke":            ["fire", "smithing", "smokehouse"],
    "sparks":           ["blacksmith", "smithing", "fire", "anvil"],

    # ------------------------------------------------------------------ #
    # TIME                                                                 #
    # ------------------------------------------------------------------ #

    "morning":          ["sunrise", "daytime", "fog"],
    "dawn":             ["sunrise", "fog"],
    "sunrise":          ["daytime"],
    "day":              ["daytime"],
    "midday":           ["daytime"],
    "afternoon":        ["daytime"],
    "evening":          ["sunset", "candle"],
    "dusk":             ["sunset", "nighttime"],
    "sunset":           ["nighttime"],
    "night":            ["nighttime", "outdoor-campfire", "candle"],
    "nighttime":        ["outdoor-campfire", "candle", "torch"],
    "dark":             ["nighttime", "interior", "dungeon"],
    "darkness":         ["nighttime", "dungeon", "torch"],

    # ------------------------------------------------------------------ #
    # WEATHER                                                              #
    # ------------------------------------------------------------------ #

    "snow":             ["daytime", "field", "road"],
    "snowing":          ["snow", "daytime"],
    "snowy":            ["snow", "field"],
    "winter":           ["snow", "indoor-fireplace"],
    "rain":             ["road", "field", "daytime"],
    "raining":          ["rain", "road"],
    "rainy":            ["rain", "field"],
    "fog":              ["sunrise", "forest", "road"],
    "foggy":            ["fog", "road", "forest"],
    "mist":             ["fog", "sunrise", "field"],
    "misty":            ["fog", "sunrise"],
    "storm":            ["thunderstorm", "rain", "nighttime"],
    "thunder":          ["thunderstorm", "nighttime"],
    "lightning":        ["thunderstorm", "nighttime"],

    # ------------------------------------------------------------------ #
    # EMOTION / STATE                                                      #
    # ------------------------------------------------------------------ #

    "angry":            ["shouting", "fighting"],
    "anger":            ["angry", "shouting"],
    "rage":             ["angry", "fighting"],
    "furious":          ["angry", "shouting"],
    "afraid":           ["fearful", "running"],
    "fear":             ["fearful"],
    "scared":           ["fearful", "running"],
    "terrified":        ["fearful", "running"],
    "cry":              ["crying"],
    "crying":           ["concerned", "family"],
    "tears":            ["crying", "concerned"],
    "weeping":          ["crying", "concerned"],
    "laugh":            ["laughing", "tavern"],
    "laughing":         ["tavern", "partying", "banquet"],
    "laughter":         ["laughing", "tavern", "partying"],
    "smile":            ["smiling", "family"],
    "smiling":          ["family", "banquet"],
    "pain":             ["painful", "wounded"],
    "painful":          ["wounded", "treating-patient"],
    "hurt":             ["painful", "wounded", "treating-patient"],
    "wound":            ["wounded", "treating-patient", "battlefield"],
    "wounded":          ["treating-patient", "battlefield", "dead"],
    "injured":          ["wounded", "treating-patient"],
    "bleeding":         ["wounded", "battlefield", "dead"],
    "sick":             ["ill", "bed", "treating-patient"],
    "ill":              ["bed", "treating-patient", "plague-doctor"],
    "disease":          ["ill", "plague-doctor", "treating-patient"],
    "plague":           ["ill", "plague-doctor", "dead"],
    "dead":             ["graveyard", "burial", "battlefield"],
    "death":            ["dead", "graveyard", "gallows"],
    "corpse":           ["dead", "battlefield", "graveyard"],
    "dying":            ["dead", "wounded", "treating-patient"],
    "hungry":           ["eating", "beggar", "market"],
    "starvation":       ["hungry", "beggar", "dead"],
    "starving":         ["hungry", "beggar"],
    "hunger":           ["hungry", "beggar", "market"],
    "cold":             ["shivering", "snow", "indoor-fireplace"],
    "freezing":         ["shivering", "snow", "outdoor-campfire"],
    "shivering":        ["snow", "nighttime", "outdoor-campfire"],
    "focused":          ["concentrated", "smithing", "writing"],
    "concentrate":      ["concentrated"],
    "concentrated":     ["smithing", "writing", "sword-training"],
    "worried":          ["concerned", "family"],
    "concern":          ["concerned"],
    "concerned":        ["family", "church", "praying"],
    "tense":            ["fighting", "sword-training", "guard"],
    "tension":          ["tense", "fighting"],
    "disgusted":        ["market", "dungeon", "prison"],
    "shout":            ["shouting", "fighting", "market"],
    "shouting":         ["fighting", "market", "crowd"],
    "yell":             ["shouting", "fighting"],
    "yelling":          ["shouting", "crowd"],
    "sweat":            ["sweaty", "smithing", "fighting"],
    "sweating":         ["sweaty", "smithing", "exercising"],

    # ------------------------------------------------------------------ #
    # THEMATISCH / ABSTRAKT                                                #
    # ------------------------------------------------------------------ #

    "war":              ["fighting", "battlefield", "army", "siege"],
    "warfare":          ["fighting", "battlefield", "army"],
    "attack":           ["fighting", "siege", "battlefield"],
    "defend":           ["guard", "wall", "shield", "castle"],
    "defense":          ["guard", "wall", "castle"],
    "punishment":       ["gallows", "prison", "crowd"],
    "journey":          ["road", "walking", "carriage", "horse"],
    "travel":           ["road", "carriage", "bridge"],
    "pilgrimage":       ["road", "praying", "church"],
    "faith":            ["praying", "church", "monk"],
    "religion":         ["church", "praying", "monk", "cross"],
    "magic":            ["alchemist", "potion", "herbs"],
    "alchemy":          ["alchemist", "potion", "workshop"],
    "medicine":         ["treating-patient", "herbs", "potion"],
    "treatment":        ["treating-patient", "bed", "herbs"],
    "ceremony":         ["church", "wedding", "crowd"],
    "ritual":           ["church", "praying", "candle"],
    "celebration":      ["partying", "banquet", "crowd"],
    "garden":           ["field", "vegetable", "gathering-herbs"],
    "gardening":        ["tilling", "field", "vegetable"],
    "storage":          ["barn", "barrel", "pantry"],
    "supplies":         ["barrel", "pantry", "food-container"],
    "crops":            ["field", "grain", "vegetable", "harvesting"],
    "livestock":        ["cow", "sheep", "pig", "chicken", "barn"],
    "animal":           ["cow", "sheep", "pig", "chicken", "horse"],
    "animals":          ["cow", "sheep", "pig", "chicken", "horse"],
    "medieval":         ["peasant", "castle", "knight", "church"],
    "ancient":          ["ruin", "stone", "castle"],
    "forgotten":        ["ruin", "graveyard"],
    "disappeared":      ["ruin", "graveyard", "dead"],
    "farm":             ["field", "barn", "peasant", "tilling"],
    "farming":          ["tilling", "field", "peasant", "harvesting"],
    "industry":         ["market", "trading", "merchant"],
    "plants":           ["field", "vegetable", "gathering-herbs"],
}


def load_models() -> dict[str, Any]:
    print("[1/4] Lade Embedding-Modell (Bi-Encoder)...")
    embedding_model = SentenceTransformer("sentence-transformers/all-mpnet-base-v2")

    print("[2/4] Lade Übersetzungsmodell (DE→EN)...")
    translation_model_name = "Helsinki-NLP/opus-mt-de-en"
    translation_tokenizer = AutoTokenizer.from_pretrained(translation_model_name)
    translation_model = AutoModelForSeq2SeqLM.from_pretrained(translation_model_name)

    print("[3/4] Lade Cross-Encoder (Reranking)...")
    cross_encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

    print("[4/4] Alle Modelle geladen.\n")

    return {
        "embedding_model": embedding_model,
        "translation_tokenizer": translation_tokenizer,
        "translation_model": translation_model,
        "cross_encoder": cross_encoder,
    }


def create_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def fetch_tag_category_map(conn: sqlite3.Connection) -> dict[str, str]:
    rows = conn.execute("""
        SELECT tag_name, category
        FROM Tags
    """).fetchall()

    return {
        row["tag_name"].lower(): (row["category"].lower() if row["category"] else "unknown")
        for row in rows
    }


def fetch_all_clips(conn: sqlite3.Connection, epoch: str | None = None) -> list[sqlite3.Row]:
    """
    Lädt alle Clips aus der DB.
    - epoch = None oder "none" → alle Clips (kein Filter)
    - epoch = "medieval" o.ä.  → nur Clips mit dieser Epoche ODER epoch IS NULL
    """
    if epoch and epoch != "none":
        return conn.execute("""
            SELECT clip_id, extension, description, embedding
            FROM Clips
            WHERE epoch = ? OR epoch IS NULL
            ORDER BY clip_id
        """, (epoch,)).fetchall()
    else:
        return conn.execute("""
            SELECT clip_id, extension, description, embedding
            FROM Clips
            ORDER BY clip_id
        """).fetchall()


def fetch_tags_by_clip(conn: sqlite3.Connection) -> dict[int, list[str]]:
    rows = conn.execute("""
        SELECT ct.clip_id, t.tag_name
        FROM ClipTag ct
        JOIN Tags t ON t.tag_id = ct.tag_id
        ORDER BY ct.clip_id, t.tag_name
    """).fetchall()

    result: dict[int, list[str]] = {}
    for row in rows:
        clip_id = row["clip_id"]
        result.setdefault(clip_id, []).append(row["tag_name"].lower())
    return result


def deserialize_embedding(blob: bytes) -> np.ndarray:
    embedding = np.frombuffer(blob, dtype=np.float32)
    if embedding.size == 0:
        raise ValueError("Embedding-BLOB konnte nicht gelesen werden.")
    return embedding


def load_clip_dataset(
    db_path: str,
    epoch: str | None = None,
) -> tuple[list[dict[str, Any]], np.ndarray, dict[str, str]]:
    epoch_info = f"Epoche: '{epoch}'" if epoch and epoch != "none" else "alle Epochen"
    print(f"Lade Clip-Datenbank aus: {db_path} ({epoch_info})")

    conn = create_connection(db_path)
    try:
        tag_category_map = fetch_tag_category_map(conn)
        clip_rows = fetch_all_clips(conn, epoch=epoch)
        tags_by_clip = fetch_tags_by_clip(conn)
    finally:
        conn.close()

    clips: list[dict[str, Any]] = []
    embeddings: list[np.ndarray] = []

    for row in clip_rows:
        clip_id = int(row["clip_id"])
        embeddings.append(deserialize_embedding(row["embedding"]))

        clips.append({
            "clip_id": clip_id,
            "description": row["description"],
            "tags": tags_by_clip.get(clip_id, []),
        })

    print(f"  → {len(clips)} Clips geladen.\n")
    return clips, np.vstack(embeddings), tag_category_map


def normalize_text(text: str) -> str:
    text = text.lower()
    replacements = {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9_]+", normalize_text(text))


def translate_sentences_de_to_en(
    sentences_de: list[str],
    translation_tokenizer: AutoTokenizer,
    translation_model: AutoModelForSeq2SeqLM,
    batch_size: int = 16,
) -> list[str]:
    print(f"Übersetze {len(sentences_de)} Sätze (Batch-Größe: {batch_size})...")
    results = []

    for batch_start in range(0, len(sentences_de), batch_size):
        batch = sentences_de[batch_start: batch_start + batch_size]
        batch_end = min(batch_start + batch_size, len(sentences_de))
        print(f"  → Batch {batch_start + 1}–{batch_end} / {len(sentences_de)}")

        inputs = translation_tokenizer(
            batch,
            return_tensors="pt",
            truncation=True,
            padding=True,
            max_length=512,
        )

        outputs = translation_model.generate(**inputs, max_length=512)

        decoded = [
            translation_tokenizer.decode(out, skip_special_tokens=True)
            for out in outputs
        ]
        results.extend(decoded)

    print(f"  → Übersetzung abgeschlossen.\n")
    return results


def sentence_similarity(
    text_a: str,
    text_b: str,
    embedding_model: SentenceTransformer,
) -> float:
    emb = embedding_model.encode([text_a, text_b], convert_to_numpy=True)
    sim = cosine_similarity([emb[0]], [emb[1]])[0][0]
    return float((sim + 1) / 2)


def expand_sentence_signals(text: str) -> list[str]:
    tokens = tokenize(text)
    expanded = []

    for token in tokens:
        if token in SIGNAL_MAP:
            expanded.extend(SIGNAL_MAP[token])

    expanded.extend(tokens)
    return expanded


def get_tag_weight(tag: str, tag_category_map: dict[str, str]) -> float:
    category = tag_category_map.get(tag.lower(), "unknown")
    return CATEGORY_WEIGHTS.get(category, 1.0)


def keyword_tag_score(
    text_en: str,
    clip_tags: list[str],
    tag_category_map: dict[str, str],
) -> tuple[float, list[tuple[str, float]]]:
    sentence_signals = expand_sentence_signals(text_en)
    if not sentence_signals:
        return 0.0, []

    score = 0.0
    clip_tag_set = set(tag.lower() for tag in clip_tags)
    matched = []

    for signal in sentence_signals:
        if signal in clip_tag_set:
            weight = get_tag_weight(signal, tag_category_map)
            score += weight
            matched.append((signal, weight))

    max_possible = sum(get_tag_weight(sig, tag_category_map) for sig in sentence_signals) + 1e-9
    return min(score / max_possible * 3.0, 1.0), matched


def combined_score(
    embedding_score: float,
    tag_score: float,
    embedding_weight: float = 0.65,
    tag_weight: float = 0.35,
) -> float:
    return embedding_weight * embedding_score + tag_weight * tag_score





def needs_context_hint(text: str) -> bool:
    text_norm = normalize_text(text)
    words = text_norm.split()
    starts_with_hint = words[0] in hint_words_exact if words else False
    contains_phrase = any(phrase in text_norm for phrase in hint_phrases)
    return starts_with_hint or contains_phrase


def score_text_against_clips(
    text_en: str,
    clips: list[dict[str, Any]],
    clip_embeddings: np.ndarray,
    embedding_model: SentenceTransformer,
    tag_category_map: dict[str, str],
    embedding_weight: float = 0.65,
    tag_weight: float = 0.35,
) -> list[dict[str, Any]]:
    text_embedding = embedding_model.encode([text_en], convert_to_numpy=True)
    similarities = cosine_similarity(text_embedding, clip_embeddings)[0]

    results = []
    for clip_index, clip in enumerate(clips):
        emb_score_raw = float(similarities[clip_index])
        emb_score_norm = (emb_score_raw + 1) / 2

        tag_score, matched_tags = keyword_tag_score(
            text_en=text_en,
            clip_tags=clip["tags"],
            tag_category_map=tag_category_map,
        )

        final_score = combined_score(
            embedding_score=emb_score_norm,
            tag_score=tag_score,
            embedding_weight=embedding_weight,
            tag_weight=tag_weight,
        )

        results.append({
            "clip_id": clip["clip_id"],
            "final_score": final_score,
            "matched_tags": matched_tags,
        })

    results.sort(key=lambda x: x["final_score"], reverse=True)
    return results


def rerank_with_cross_encoder(
    text_en: str,
    candidate_clip_ids: list[int],
    candidate_scores: list[float],
    clips: list[dict[str, Any]],
    cross_encoder: CrossEncoder,
    top_n: int = 20,
    bi_weight: float = 0.4,
    cross_weight: float = 0.6,
    confidence_threshold: float = 0.65,
) -> list[int]:
    clip_map = {c["clip_id"]: c for c in clips}

    top_score = max(candidate_scores) if candidate_scores else 0.0
    if top_score < confidence_threshold:
        actual_bi_weight = 0.75
        actual_cross_weight = 0.25
        print(f"  Niedriger Confidence-Score ({top_score:.3f}) → Bi-Encoder bevorzugt (0.75/0.25)")
    else:
        actual_bi_weight = bi_weight
        actual_cross_weight = cross_weight

    pairs = [
        (text_en, clip_map[cid]["description"])
        for cid in candidate_clip_ids
        if cid in clip_map
    ]

    cross_scores = cross_encoder.predict(pairs)

    cross_min, cross_max = min(cross_scores), max(cross_scores)
    cross_norm = [
        (s - cross_min) / (cross_max - cross_min + 1e-9)
        for s in cross_scores
    ]

    combined = [
        actual_bi_weight * bi_score + actual_cross_weight * cross_score
        for bi_score, cross_score in zip(candidate_scores, cross_norm)
    ]

    ranked = sorted(
        zip(candidate_clip_ids, combined),
        key=lambda x: x[1],
        reverse=True,
    )
    return [cid for cid, _ in ranked[:top_n]]


def find_best_clip_ids_for_sentences(
    sentences_de: list[str],
    db_path: str,
    top_k: int = 3,
    epoch: str | None = None,
    bi_encoder_candidates: int = 50,
    reranker_top_n: int = 20,
    context_threshold: float = 0.58,
    similarity_threshold: float = 0.62,
    embedding_weight: float = 0.65,
    tag_weight: float = 0.35,
) -> list[list[int]]:
    """
    Rückgabe:
    [
        [12, 7, 4],
        [6, 21, 7],
        [16, 14, 18]
    ]

    Pipeline:
    1. Bi-Encoder wählt die besten `bi_encoder_candidates` (z.B. 50) Clips pro Satz
    2. Cross-Encoder rerankt diese auf `reranker_top_n` (z.B. 20)
    3. Die finalen Top-`top_k` IDs werden zurückgegeben

    epoch: filtert Clips nach Epoche (+ epochenlose Clips).
           None oder "none" = kein Filter.
    """

    if not sentences_de:
        return []

    print("=== Clip-Matching gestartet ===\n")

    models = load_models()
    embedding_model = models["embedding_model"]
    translation_tokenizer = models["translation_tokenizer"]
    translation_model = models["translation_model"]
    cross_encoder = models["cross_encoder"]

    clips, clip_embeddings, tag_category_map = load_clip_dataset(db_path, epoch=epoch)

    if not clips:
        print("WARNUNG: Keine Clips für diese Epoche gefunden.")
        return [[] for _ in sentences_de]

    sentences_en = translate_sentences_de_to_en(
        sentences_de=sentences_de,
        translation_tokenizer=translation_tokenizer,
        translation_model=translation_model,
    )

    all_top_clip_ids: list[list[int]] = []
    total = len(sentences_en)

    print(f"Verarbeite {total} Sätze...\n")

    for i, sentence_en in enumerate(sentences_en):
        print(f"[Satz {i + 1}/{total}] \"{sentence_en[:80]}{'...' if len(sentence_en) > 80 else ''}\"")

        # --- Schritt 1: Bi-Encoder → Top-50 Kandidaten ---
        base_results = score_text_against_clips(
            text_en=sentence_en,
            clips=clips,
            clip_embeddings=clip_embeddings,
            embedding_model=embedding_model,
            tag_category_map=tag_category_map,
            embedding_weight=embedding_weight,
            tag_weight=tag_weight,
        )
        base_best = base_results[0]

        print(f"  Bi-Encoder: bester Score = {base_best['final_score']:.4f} (Clip {base_best['clip_id']})")

        chosen_results = base_results

        # --- Rückwärts-Kontext ---
        if i > 0:
            prev_en = sentences_en[i - 1]
            sim_prev_current = sentence_similarity(
                text_a=prev_en,
                text_b=sentence_en,
                embedding_model=embedding_model,
            )
            hint = needs_context_hint(sentence_en)

            if base_best["final_score"] < context_threshold and (
                sim_prev_current >= similarity_threshold or hint
            ):
                print(f"  Rückwärts-Kontext aktiv (sim={sim_prev_current:.3f}, hint={hint})")
                context_text_en = prev_en + " " + sentence_en

                context_results = score_text_against_clips(
                    text_en=context_text_en,
                    clips=clips,
                    clip_embeddings=clip_embeddings,
                    embedding_model=embedding_model,
                    tag_category_map=tag_category_map,
                    embedding_weight=embedding_weight,
                    tag_weight=tag_weight,
                )

                if context_results[0]["final_score"] > base_best["final_score"]:
                    print(f"  Rückwärts-Kontext verbessert Score: {context_results[0]['final_score']:.4f}")
                    chosen_results = context_results

        # --- Vorwärts-Kontext ---
        if base_best["final_score"] < context_threshold and i < len(sentences_en) - 1:
            next_en = sentences_en[i + 1]
            incomplete = (
                sentence_en.strip().endswith("–") or
                sentence_en.strip().endswith("...") or
                len(sentence_en.split()) < 6
            )
            if incomplete:
                print(f"  Vorwärts-Kontext aktiv (unvollständiger Satz erkannt)")
                context_text_en = sentence_en + " " + next_en
                forward_results = score_text_against_clips(
                    text_en=context_text_en,
                    clips=clips,
                    clip_embeddings=clip_embeddings,
                    embedding_model=embedding_model,
                    tag_category_map=tag_category_map,
                    embedding_weight=embedding_weight,
                    tag_weight=tag_weight,
                )
                if forward_results[0]["final_score"] > base_best["final_score"]:
                    print(f"  Vorwärts-Kontext verbessert Score: {forward_results[0]['final_score']:.4f}")
                    chosen_results = forward_results

        # --- Schritt 2: Top-50 Kandidaten sammeln ---
        candidate_ids = [entry["clip_id"] for entry in chosen_results[:bi_encoder_candidates]]
        candidate_scores = [entry["final_score"] for entry in chosen_results[:bi_encoder_candidates]]

        # Top 10 vor Cross-Encoder
        print(f"  Top 10 vor Cross-Encoder:")
        for rank, entry in enumerate(chosen_results[:10], start=1):
            tags_str = ", ".join(
                f"{t}({w:.1f})" for t, w in entry["matched_tags"]
            ) if entry["matched_tags"] else "–"
            print(f"    #{rank:02d} Clip {entry['clip_id']:>4d} | "
                  f"Score: {entry['final_score']:.4f} | Tags: {tags_str}")

        # --- Schritt 3: Cross-Encoder → Top-20 reranken ---
        print(f"  Cross-Encoder rerankt {len(candidate_ids)} Kandidaten → Top {reranker_top_n}...")
        reranked_ids = rerank_with_cross_encoder(
            text_en=sentence_en,
            candidate_clip_ids=candidate_ids,
            candidate_scores=candidate_scores,
            clips=clips,
            cross_encoder=cross_encoder,
            top_n=reranker_top_n,
        )

        # --- Schritt 4: Finale Top-k ---
        top_clip_ids = reranked_ids[:top_k]
        print(f"  → Finale Top-{top_k} Clip-IDs: {top_clip_ids}\n")

        all_top_clip_ids.append(top_clip_ids)

    print("=== Clip-Matching abgeschlossen ===")
    return all_top_clip_ids