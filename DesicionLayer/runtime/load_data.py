import csv
from typing import Dict
from model.definitions.Catalog import Catalog 
from model.definitions.ActorDef import ActorDef
from model.definitions.ItemDef import ItemDef
from model.definitions.LocationDef import LocationDef


def load_actors(csv_path: str = "data/actor.csv") -> Dict[str, ActorDef]:
    actors: Dict[str, ActorDef] = {}
    with open(csv_path, newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            actor_id = row["actorId"].strip()
            if not actor_id:
                continue
            actors[actor_id] = ActorDef(
                id=actor_id,
                name=row["name"].strip(),
                gender=row["gender"].strip(),
                age=int(row["age"]),
                info=row["info"].strip(),
                skill=row["skill"].strip(),
            )
    return actors


def load_items(csv_path: str = "data/item.csv") -> Dict[str, ItemDef]:
    items : Dict[str, ItemDef] = {}
    with open(csv_path, newline="",encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            item_id = row["itemId"].strip()
            if not item_id:
                continue
            effects = {
                "hunger": int(row["hunger"]),
                "thirst": int(row["thirst"]),
                "energy": int(row["energy"]),
            }
            items[item_id] = ItemDef(
                id=item_id,
                name=row["name"].strip(),
                category=row["category"].strip(),
                base_price=float(row["basePrice"]),
                sell_ratio=float(row["sellRatio"]),
                description=row["description"].strip(),
                effects=effects
            )
    return items

def load_locations(csv_path: str = "data/location.csv") -> Dict[str, LocationDef]:
    location :Dict[str, LocationDef] = {}
    alias_map = {
        "marketcomponent": "market",
        "market": "market",
    }
    with open(csv_path, newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            location_id = row["locationId"].strip()
            if not location_id:
                continue
            components_raw = (row.get("components") or row.get("component") or "").strip()
            components = []
            for raw in components_raw.split("/"):
                comp = raw.strip()
                if not comp:
                    continue
                key = alias_map.get(comp.lower(), comp.lower())
                components.append(key)
            location[location_id] = LocationDef(
                id=location_id,
                name=row["name"].strip(),
                description=row["description"].strip(),
                components=components
            )
    return location

def load_catalog() -> Catalog:
    """Load the catalog from the CSV files."""
    actors = load_actors()
    items = load_items()
    locations = load_locations()
    return Catalog(items=items, locations=locations, actors=actors)
