from copy import copy
from enum import Enum

import langcodes
import pony.orm.dbapiprovider
from pony import orm


class RelationName(Enum):
    RELATED_TO = 'related_to'
    FORM_OF = 'form_of'
    IS_A = 'is_a'
    PART_OF = 'part_of'
    HAS_A = 'has_a'
    USED_FOR = 'used_for'
    CAPABLE_OF = 'capable_of'
    AT_LOCATION = 'at_location'
    CAUSES = 'causes'
    HAS_SUBEVENT = 'has_subevent'
    HAS_FIRST_SUBEVENT = 'has_first_subevent'
    HAS_LAST_SUBEVENT = 'has_last_subevent'
    HAS_PREREQUISITE = 'has_prerequisite'
    HAS_PROPERTY = 'has_property'
    MOTIVATED_BY_GOAL = 'motivated_by_goal'
    OBSTRUCTED_BY = 'obstructed_by'
    DESIRES = 'desires'
    CREATED_BY = 'created_by'
    SYNONYM = 'synonym'
    ANTONYM = 'antonym'
    DISTINCT_FROM = 'distinct_from'
    DERIVED_FROM = 'derived_from'
    SYMBOL_OF = 'symbol_of'
    DEFINED_AS = 'defined_as'
    MANNER_OF = 'manner_of'
    LOCATED_NEAR = 'located_near'
    HAS_CONTEXT = 'has_context'
    SIMILAR_TO = 'similar_to'
    ETYMOLOGICALLY_RELATED_TO = 'etymologically_related_to'
    ETYMOLOGICALLY_DERIVED_FROM = 'etymologically_derived_from'
    CAUSES_DESIRE = 'causes_desire'
    MADE_OF = 'made_of'
    RECEIVES_ACTION = 'receives_action'
    EXTERNAL_URL = 'external_url'


class EnumConverter(orm.dbapiprovider.StrConverter):
    def validate(self, val, obj=None):
        if not isinstance(val, Enum):
            raise ValueError('Must be an enum.Enum. Got {}'.format(type(val)))
        return val

    def py2sql(self, val):
        return val.name

    def sql2py(self, value):
        return self.py_type[value]


class LanguageConverter(orm.dbapiprovider.StrConverter):
    def validate(self, val, obj=None):
        val = langcodes.Language.get(val)
        if not isinstance(val, langcodes.Language):
            raise ValueError('Must be an langcodes.Language. Got {}'.format(type(val)))
        return val

    def py2sql(self, val: langcodes.Language):
        return str(val)

    def sql2py(self, value):
        return langcodes.Language.get(value)


db = orm.Database()


class Relation(db.Entity):
    id = orm.PrimaryKey(int, auto=True)
    name = orm.Required(RelationName, unique=True)
    edges = orm.Set('Edge')

    @property
    def uri(self) -> str:
        return f'/r/{self.name.value}'


class Concept(db.Entity):
    id = orm.PrimaryKey(int, auto=True)
    edges_out = orm.Set('Edge', reverse='start')
    edges_in = orm.Set('Edge', reverse='end')
    label = orm.Required('Label')
    sense_label = orm.Optional(str)

    @property
    def uri(self) -> str:
        ending = f'/{self.sense_label}' if self.sense_label else ''
        return f'/c/{self.label.language.name}/{self.label.text}{ending}'


class Edge(db.Entity):
    id = orm.PrimaryKey(int, auto=True)
    relation = orm.Required(Relation)
    start = orm.Required(Concept, reverse='edges_out')
    end = orm.Required(Concept, reverse='edges_in')
    etc = orm.Optional(orm.Json)

    @property
    def uri(self) -> str:
        return f'/a/[{self.relation.uri}/,{self.start.uri}/,{self.end.uri}/]'


class Language(db.Entity):
    id = orm.PrimaryKey(int, auto=True)
    name = orm.Required(langcodes.Language)
    labels = orm.Set('Label')


class Label(db.Entity):
    id = orm.PrimaryKey(int, auto=True)
    text = orm.Required(str)
    language = orm.Required(Language)
    concepts = orm.Set(Concept)
