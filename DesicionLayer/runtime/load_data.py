"""从 CSV 读取静态定义，并组装 Catalog。"""

import csv
from typing import Dict
from model.definitions.Catalog import Catalog 
from model.definitions.ActorDef import ActorDef
from model.definitions.ItemDef import ItemDef
from model.definitions.LocationDef import LocationDef


def load_actors(csv_path: str = "data/actor.csv") -> Dict[str, ActorDef]:
    # actor.csv -> ActorDef 字典（key 为 actorId）。
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
    # item.csv -> ItemDef；effects 字段在这里归并为统一 dict。
    items : Dict[str, ItemDef] = {}
    with open(csv_path, newline="",encoding="utf-8") as csvfile:
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
                effects=effects
            )
    return items

def load_locations(csv_path: str = "data/location.csv") -> Dict[str, LocationDef]:
    # location.csv -> LocationDef。
    location :Dict[str, LocationDef] = {}
    with open(csv_path, newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            location_id = row["locationId"]
            if not location_id:
                continue
            
            location[location_id] = LocationDef(
                id=location_id,
                name=row["name"],
                description=row["description"],
                type=row["type"]
            )
    return location

def load_catalog() -> Catalog:
    """聚合三个 CSV 的读取结果。"""
    actors = load_actors()
    items = load_items()
    locations = load_locations()
    return Catalog(items=items, locations=locations, actors=actors)
