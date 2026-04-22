"""Load static definitions from CSV/JSON and compose Catalog."""

import csv
import json
from typing import Dict, Tuple

from model.definitions.ActorDef import ActorDef
from model.definitions.Catalog import Catalog
from model.definitions.ItemDef import ItemDef
from model.definitions.LocationDef import LocationDef

HUMAN_SHOP_ASSISTANT_ACTOR_ID = "actor:shop_assistant_human"
HUMAN_SHOP_ASSISTANT_ACTOR_NAME = "ShopAssistant"


def load_actors(csv_path: str = "data/actor.csv") -> Dict[str, ActorDef]:
    actors: Dict[str, ActorDef] = {}
    with open(csv_path, newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            actor_id = row["actorId"]
            if not actor_id:
                continue
            actors[actor_id] = ActorDef(
                id=actor_id,
                name=row["name"],
                gender=row["gender"],
                age=int(row["age"]),
                info=row["info"],
                skill=row["skill"],
            )
    return actors


def load_items(csv_path: str = "data/item.csv") -> Dict[str, ItemDef]:
    items: Dict[str, ItemDef] = {}
    with open(csv_path, newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            item_id = row["itemId"]
            if not item_id:
                continue
            effects = {
                "hunger": int(row["hunger"]),
                "thirst": int(row["thirst"]),
                "fatigue": int(row["fatigue"]),
            }
            items[item_id] = ItemDef(
                id=item_id,
                name=row["name"],
                category=row["category"],
                base_price=float(row["basePrice"]),
                sell_ratio=float(row["sellRatio"]),
                description=row["description"],
                default_quantity=int(row["quantity"]),
                effects=effects,
            )
    return items


def load_locations(csv_path: str = "data/location.csv") -> Dict[str, LocationDef]:
    locations: Dict[str, LocationDef] = {}
    with open(csv_path, newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            location_id = row["locationId"]
            if not location_id:
                continue

            locations[location_id] = LocationDef(
                id=location_id,
                name=row["name"],
                description=row["description"],
                type=row["type"],
            )
    return locations


def load_events(json_path: str = "data/event.json") -> Tuple[dict, dict]:
    random_events = {}
    skill_events = {}
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        for event in data:
            if event["source"] == "random_event":
                random_events[event["id"]] = event
            elif event["source"] == "skill":
                skill_events[event["id"]] = event
    return random_events, skill_events


def load_catalog() -> Catalog:
    actors = load_actors()

    # Inject human shop assistant actor for Unity/Python identity alignment.
    if HUMAN_SHOP_ASSISTANT_ACTOR_ID not in actors:
        actors[HUMAN_SHOP_ASSISTANT_ACTOR_ID] = ActorDef(
            id=HUMAN_SHOP_ASSISTANT_ACTOR_ID,
            name=HUMAN_SHOP_ASSISTANT_ACTOR_NAME,
            gender="",
            age=0,
            info="",
            skill="",
        )

    items = load_items()
    locations = load_locations()
    random_events, skill_events = load_events()
    return Catalog(items=items, locations=locations, actors=actors, random_events=random_events, skill_events=skill_events)
