"""Registry of the supported ``.bin`` formats."""

from __future__ import annotations

from typing import Iterable

from ..codec import Codec
from .achieve import AchieveCodec
from .battletable import BattleTableCodec
from .buff import BuffCodec
from .cashshop import CashShopCodec
from .charcreatetable import CharCreateTableCodec
from .dmbase import DMBaseCodec
from .digimon_list import DigimonListCodec
from .digimonevo import DigimonEvoCodec
from .digimonparcel import DigimonParcelCodec
from .effectlist import EffectListCodec
from .event import EventCodec
from .extraexchange import ExtraExchangeCodec
from .itemlist import ItemListCodec
from .maplist import MapListCodec
from .mapmonsterlist import MapMonsterListCodec
from .mapnpc import MapNpcCodec
from .mapobject import MapObjectCodec
from .mapregion import MapRegionCodec
from .monster import MonsterCodec
from .nature import NatureCodec
from .newelement import NewElementCodec
from .npc import NpcCodec
from .portal import MapPortalCodec
from .quest import QuestCodec
from .ride import RideCodec
from .servertransfer import ServerTransferCodec
from .skill import SkillCodec
from .timecharge import TimeChargeCodec
from .uitext import UITextCodec
from .worldmap import WorldMapCodec

CODECS: tuple[Codec, ...] = (
    AchieveCodec(),
    BattleTableCodec(),
    BuffCodec(),
    CashShopCodec(),
    CharCreateTableCodec(),
    DMBaseCodec(),
    DigimonListCodec(),
    DigimonEvoCodec(),
    DigimonParcelCodec(),
    EffectListCodec(),
    EventCodec(),
    ExtraExchangeCodec(),
    ItemListCodec(),
    MapListCodec(),
    MapMonsterListCodec(),
    MapNpcCodec(),
    MapObjectCodec(),
    MapPortalCodec(),
    MapRegionCodec(),
    MonsterCodec(),
    NatureCodec(),
    NewElementCodec(),
    NpcCodec(),
    QuestCodec(),
    RideCodec(),
    ServerTransferCodec(),
    SkillCodec(),
    TimeChargeCodec(),
    UITextCodec(),
    WorldMapCodec(),
)

_BY_FILENAME = {stem: codec for codec in CODECS for stem in codec.filenames}
_BY_NAME = {codec.name: codec for codec in CODECS}


def for_filename(filename: str) -> Codec | None:
    """Return the codec for a ``.bin``/``.dat`` file name (extension ignored)."""

    stem = filename.replace("\\", "/").rsplit("/", 1)[-1]
    if "." in stem:
        stem = stem.rsplit(".", 1)[0]
    return _BY_FILENAME.get(stem.lower())


def by_name(name: str) -> Codec | None:
    return _BY_NAME.get(name)


def for_stem(stem: str) -> Codec | None:
    """Return the codec for a format folder / file stem such as ``ItemList``."""

    return _BY_NAME.get(stem) or _BY_FILENAME.get(stem.lower())


def names() -> list[str]:
    return sorted(_BY_NAME)


def all_codecs() -> Iterable[Codec]:
    return CODECS
