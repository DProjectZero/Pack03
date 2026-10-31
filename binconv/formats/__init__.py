"""Registry of the supported ``.bin`` formats."""

from __future__ import annotations

from typing import Iterable

from ..codec import Codec
from .achieve import AchieveCodec
from .addexp import AddExpCodec
from .battletable import BattleTableCodec
from .buff import BuffCodec
from .cashshop import CashShopCodec
from .charcreatetable import CharCreateTableCodec
from .cuid import CuidCodec
from .dmbase import DMBaseCodec
from .dataexchange import DataExchangeCodec
from .digimon_book import DigimonBookCodec
from .digimon_list import DigimonListCodec
from .digimonevo import DigimonEvoCodec
from .digimonparcel import DigimonParcelCodec
from .effectlist import EffectListCodec
from .event import EventCodec
from .extraexchange import ExtraExchangeCodec
from .gotcha import GotchaCodec
from .infinitewar import InfiniteWarCodec
from .itemlist import ItemListCodec
from .mapcharlight import MapCharLightCodec
from .maplist import MapListCodec
from .mastercard import MasterCardCodec
from .mapmonsterlist import MapMonsterListCodec
from .mapnpc import MapNpcCodec
from .mapobject import MapObjectCodec
from .mapregion import MapRegionCodec
from .monster import MonsterCodec
from .nature import NatureCodec
from .newelement import NewElementCodec
from .npc import NpcCodec
from .passiveability import PassiveAbilityCodec
from .portal import MapPortalCodec
from .quest import QuestCodec
from .reward import RewardCodec
from .ride import RideCodec
from .scene import SceneCodec
from .servertransfer import ServerTransferCodec
from .skill import SkillCodec
from .spiritnpc import SpiritNpcCodec
from .svlineup import SvLineUpCodec
from .tactics import TacticsCodec
from .talk import TalkCodec
from .tamerlist import TamerListCodec
from .timecharge import TimeChargeCodec
from .tutorial import TutorialCodec
from .uitext import UITextCodec
from .weather import WeatherCodec
from .worldmap import WorldMapCodec

CODECS: tuple[Codec, ...] = (
    AchieveCodec(),
    AddExpCodec(),
    BattleTableCodec(),
    BuffCodec(),
    CashShopCodec(),
    CharCreateTableCodec(),
    CuidCodec(),
    DMBaseCodec(),
    DataExchangeCodec(),
    DigimonBookCodec(),
    DigimonListCodec(),
    DigimonEvoCodec(),
    DigimonParcelCodec(),
    EffectListCodec(),
    EventCodec(),
    ExtraExchangeCodec(),
    GotchaCodec(),
    InfiniteWarCodec(),
    ItemListCodec(),
    MapCharLightCodec(),
    MapListCodec(),
    MasterCardCodec(),
    MapMonsterListCodec(),
    MapNpcCodec(),
    MapObjectCodec(),
    MapPortalCodec(),
    MapRegionCodec(),
    MonsterCodec(),
    NatureCodec(),
    NewElementCodec(),
    NpcCodec(),
    PassiveAbilityCodec(),
    QuestCodec(),
    RewardCodec(),
    RideCodec(),
    SceneCodec(),
    ServerTransferCodec(),
    SkillCodec(),
    SpiritNpcCodec(),
    SvLineUpCodec(),
    TacticsCodec(),
    TalkCodec(),
    TamerListCodec(),
    TimeChargeCodec(),
    TutorialCodec(),
    UITextCodec(),
    WeatherCodec(),
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
