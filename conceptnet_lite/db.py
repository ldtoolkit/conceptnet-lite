import csv
import gzip
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, Generator, Tuple, Type

import langcodes
import pony.orm.dbapiprovider
from pony import orm
from pySmartDL import SmartDL

from conceptnet_lite.utils import PathOrStr, to_snake_case


class RelationName:
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
    name = orm.Required(str, unique=True)
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

    @property
    def language(self) -> 'Language':
        return self.label.language

    @property
    def text(self) -> str:
        return self.label.text


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


def open_db(path: PathOrStr, create_db: bool = False):
    db.bind(provider='sqlite', filename=str(path), create_db=create_db)
    db.provider.converter_classes.append((langcodes.Language, LanguageConverter))
    db.generate_mapping(create_tables=True)


CONCEPTNET_DOWNLOAD_URL = 'https://s3.amazonaws.com/conceptnet/downloads/2019/edges/conceptnet-assertions-5.7.0.csv.gz'


def download_dump(
    url: str = CONCEPTNET_DOWNLOAD_URL,
    dir_path: PathOrStr = Path.cwd(),
    progress_bar: bool = True,
):
    print("Download compressed dump")
    compressed_dump_downloader = SmartDL(url, str(dir_path), progress_bar=progress_bar)
    compressed_dump_path = Path(compressed_dump_downloader.dest)
    if not compressed_dump_path.is_file():
        shutil.rmtree(str(compressed_dump_path), ignore_errors=True)
        compressed_dump_downloader.start()


def unpack_dump(
    compressed_dump_path: PathOrStr,
    delete_compressed_dump: bool = True,
):
    print("Uncompress compressed dump")
    dump_path = Path(compressed_dump_path).with_suffix('')
    with gzip.open(str(compressed_dump_path), 'rb') as f_in:
        with open(str(dump_path), 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)
    if delete_compressed_dump:
        compressed_dump_path.unlink()


@orm.db_session
def load_dump_to_db(
    dump_path: PathOrStr,
    edges_count: Optional[int] = None,
    delete_dump: bool = True,
):
    def edges_from_dump_by_parts_generator(
            path: PathOrStr,
            count: Optional[int] = None,
    ) -> Generator[Tuple[str, str, str, str], None, None]:
        with open(str(path), newline='') as f:
            reader = csv.reader(f, delimiter='\t')
            for i, row in enumerate(reader):
                yield row[1:5]
                if i == count:
                    break

    def extract_relation_name(uri: str) -> str:
        return to_snake_case(uri.rpartition('/')[-1])

    def get_or_create(entity_cls: Type[db.Entity], **kwargs):
        return entity_cls.get(**kwargs) or entity_cls(**kwargs)

    def get_or_create_concept(uri: str) -> Concept:
        split_url = uri.split('/', maxsplit=4)
        language = get_or_create(Language, name=split_url[2])
        label = get_or_create(Label, text=split_url[3], language=language)
        concept = get_or_create(Concept, label=label, sense_label=('' if len(split_url) == 4 else split_url[4]))
        return concept

    dump_loading_start = datetime.now()
    print("Load dump to database")
    for relation_name, start_uri, end_uri, edge_etc_json in (
            edges_from_dump_by_parts_generator(path=dump_path, count=edges_count)):
        relation = get_or_create(Relation, name=extract_relation_name(relation_name))
        start = get_or_create_concept(uri=start_uri)
        end = get_or_create_concept(uri=end_uri)
        edge = get_or_create(Edge, relation=relation, start=start, end=end)
        edge.etc = json.loads(edge_etc_json)
    dump_loading_end = datetime.now()
    print("Time for loading dump:", dump_loading_end - dump_loading_start)

    if delete_dump:
        dump_path.unlink()


def prepare_db(
        db_path: PathOrStr,
        dump_dir_path: PathOrStr = Path.cwd(),
        download_url: str = CONCEPTNET_DOWNLOAD_URL,
        download_progress_bar: bool = True,
        load_dump_edges_count: Optional[int] = None,
        delete_compressed_dump: bool = True,
        delete_dump: bool = True,
):
    db_path = Path(db_path).expanduser().resolve()
    dump_dir_path = Path(dump_dir_path).expanduser().resolve()
    compressed_dump_path = dump_dir_path / Path(CONCEPTNET_DOWNLOAD_URL.rpartition('/')[-1])
    dump_path = compressed_dump_path.with_suffix('')

    db_path.parent.mkdir(parents=True, exist_ok=True)
    dump_dir_path.mkdir(parents=True, exist_ok=True)

    open_db(path=db_path, create_db=True)

    try:
        load_dump_to_db(dump_path=dump_path, edges_count=load_dump_edges_count, delete_dump=delete_dump)
    except FileNotFoundError as e:
        print(str(e).replace('[Errno 2] ', '', 1))
        try:
            unpack_dump(compressed_dump_path=compressed_dump_path, delete_compressed_dump=delete_compressed_dump)
            load_dump_to_db(dump_path=dump_path, edges_count=load_dump_edges_count, delete_dump=delete_dump)
        except FileNotFoundError as e:
            print(str(e).replace('[Errno 2] ', '', 1))
            download_dump(url=download_url, dir_path=dump_dir_path, progress_bar=download_progress_bar)
            unpack_dump(compressed_dump_path=compressed_dump_path, delete_compressed_dump=delete_compressed_dump)
            load_dump_to_db(dump_path=dump_path, edges_count=load_dump_edges_count, delete_dump=delete_dump)
