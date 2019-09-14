import csv
import gzip
import shutil
import struct
import zipfile
from functools import partial
from pathlib import Path
from typing import Optional, Generator, Tuple
from uuid import uuid4

import lmdb
from pySmartDL import SmartDL
from tqdm import tqdm
from peewee import DatabaseProxy, Model, TextField, ForeignKeyField
from playhouse.sqlite_ext import JSONField, SqliteExtDatabase

from conceptnet_lite.utils import PathOrStr, _to_snake_case


class RelationName:
    """Names of non-deprecated relations.

    See: https://github.com/commonsense/conceptnet5/wiki/Relations.
    """

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


db = DatabaseProxy()


class _BaseModel(Model):
    class Meta:
        database = db


class Relation(_BaseModel):
    """Relation ORM class.

    See: https://github.com/commonsense/conceptnet5/wiki/Relations.
    """

    name = TextField(unique=True)

    @property
    def uri(self) -> str:
        return f'/r/{self.name}'


class Language(_BaseModel):
    """Language ORM class.

    See: https://github.com/commonsense/conceptnet5/wiki/Languages.
    """

    name = TextField(unique=True)


class Label(_BaseModel):
    """Label ORM class.

    :class:`Label` can be seen as a part of :class:`Concept`. :class:`Label` is basically a text on a certain language
    (most often, a word).

    This abstraction is not present in the original ConceptNet. Class is introduced for the purposes of normalization.
    """

    text = TextField(index=True)
    language = ForeignKeyField(Language, backref='labels')


class Concept(_BaseModel):
    """Concept ORM class.

    :class:`Concept` represents node in ConceptNet knowledge graph. It provides properties :attr:`language` and
    :attr:`text` that are aliases for corresponding :attr:`Label.language` and :attr:`Label.text` fields.

    This abstraction is not present in the original ConceptNet. Class is introduced for the purposes of normalization.
    """

    label = ForeignKeyField(Label, backref='concepts')
    sense_label = TextField()

    @property
    def uri(self) -> str:
        ending = f'/{self.sense_label}' if self.sense_label else ''
        return f'/c/{self.language.name}/{self.text}{ending}'

    @property
    def language(self) -> Language:
        return self.label.language

    @property
    def text(self) -> str:
        return self.label.text


class Edge(_BaseModel):
    """Edge ORM class.

    See: https://github.com/commonsense/conceptnet5/wiki/Edges.

    Everything except relation, start, and end nodes is stored in :attr:`etc` field that is plain :class:`dict`.
    """

    relation = ForeignKeyField(Relation, backref='edges')
    start = ForeignKeyField(Concept, backref='edges_out')
    end = ForeignKeyField(Concept, backref='edges_in')
    etc = JSONField()

    @property
    def uri(self) -> str:
        return f'/a/[{self.relation.uri}/,{self.start.uri}/,{self.end.uri}/]'


def _open_db(path: PathOrStr):
    db.initialize(SqliteExtDatabase(str(path), pragmas={
        'synchronous': 0,
        'cache_size': -1024 * 64,
    }))
    tables = [Relation, Language, Label, Concept, Edge]
    db.create_tables(tables)


# For ConceptNet 5.7:
CONCEPTNET_DUMP_DOWNLOAD_URL = (
    'https://s3.amazonaws.com/conceptnet/downloads/2019/edges/conceptnet-assertions-5.7.0.csv.gz')
CONCEPTNET_DB_URL = 'https://conceptnet-lite.fra1.cdn.digitaloceanspaces.com/conceptnet.db.zip'
CONCEPTNET_EDGE_COUNT = 34074917
CONCEPTNET_DB_NAME = 'conceptnet.db'


def _get_download_destination_path(dir_path: Path, url: str) -> Path:
    return dir_path / url.rsplit('/')[-1]


def download_dump(
    url: str = CONCEPTNET_DUMP_DOWNLOAD_URL,
    out_dir_path: PathOrStr = Path.cwd(),
):
    """Download compressed ConceptNet dump.

    Args:
        url: Link to the dump.
        out_dir_path: Dir where to store dump.
    """

    print("Download compressed dump")
    compressed_dump_path = _get_download_destination_path(out_dir_path, url)
    if compressed_dump_path.is_file():
        raise FileExistsError(17, "File already exists", str(compressed_dump_path))
    downloader = SmartDL(url, str(compressed_dump_path))
    downloader.start()


def extract_compressed_dump(
    compressed_dump_path: PathOrStr,
    delete_compressed_dump: bool = True,
):
    """Extract compressed ConceptNet dump.

    Args:
          compressed_dump_path: Path to compressed dump to extract.
          delete_compressed_dump: Delete compressed dump after extraction.
    """

    dump_path = Path(compressed_dump_path).with_suffix('')
    try:
        with gzip.open(str(compressed_dump_path), 'rb') as f_in:
            with open(str(dump_path), 'wb') as f_out:
                print("Extract compressed dump (this can take a few minutes)")
                shutil.copyfileobj(f_in, f_out)
    finally:
        if delete_compressed_dump and compressed_dump_path.is_file():
            compressed_dump_path.unlink()


def load_dump_to_db(
    dump_path: PathOrStr,
    db_path: PathOrStr,
    edge_count: int = CONCEPTNET_EDGE_COUNT,
    delete_dump: bool = True,
):
    """Load dump to database.

    Args:
          dump_path: Path to dump to load.
          db_path: Path to resulting database.
          edge_count: Number of edges to load from the beginning of the dump file. Can be useful for testing.
          delete_dump: Delete dump after loading into database.
    """

    def edges_from_dump_by_parts_generator(
            count: Optional[int] = None,
    ) -> Generator[Tuple[str, str, str, str], None, None]:
        with open(str(dump_path), newline='') as f:
            reader = csv.reader(f, delimiter='\t')
            for i, row in enumerate(reader):
                if i == count:
                    break
                yield row[1:5]

    def extract_relation_name(uri: str) -> str:
        return _to_snake_case(uri[3:])

    def get_struct_format(length: int) -> str:
        return f'{length}Q'

    def pack_ints(*ints) -> bytes:
        return struct.pack(get_struct_format(length=len(ints)), *ints)

    def unpack_ints(buffer: bytes) -> Tuple[int, ...]:
        return struct.unpack(get_struct_format(len(buffer) // 8), buffer)

    def relation_in_bytes(relation_uri: str) -> bytes:
        relation_name = extract_relation_name(relation_uri)
        return relation_name.encode('utf8')

    def language_and_label_in_bytes(concept_uri: str) -> Tuple[bytes, bytes]:
        return tuple(x.encode('utf8') for x in concept_uri.split('/', maxsplit=4)[2:4])[:2]

    def normalize() -> None:
        """Normalize dump before loading into database using lmdb."""

        def normalize_relation() -> None:
            nonlocal relation_i

            relation_b = relation_in_bytes(relation_uri=relation_uri)
            relation_exists = txn.get(relation_b, db=relation_db) is not None
            if not relation_exists:
                relation_i += 1
                relation_i_b = pack_ints(relation_i)
                txn.put(relation_b, relation_i_b, db=relation_db)

        def normalize_concept(uri: str) -> None:
            nonlocal language_i, label_i, concept_i

            language_b, label_b = language_and_label_in_bytes(concept_uri=uri)

            language_id_b = txn.get(language_b, db=language_db)
            if language_id_b is None:
                language_i += 1
                language_id_b = pack_ints(language_i)
                txn.put(language_b, language_id_b, db=language_db)

            label_language_b = label_b + b'/' + language_b
            label_id_b = txn.get(label_language_b, db=label_db)
            if label_id_b is None:
                label_i += 1
                label_id_b = pack_ints(label_i)
                txn.put(label_language_b, label_id_b, db=label_db)

            concept_b = uri.encode('utf8')
            concept_id_b = txn.get(concept_b, db=concept_db)
            if concept_id_b is None:
                concept_i += 1
                concept_id_b = pack_ints(concept_i)
                txn.put(concept_b, concept_id_b, db=concept_db)

        language_i, relation_i, label_i, concept_i = 4 * [0]
        if not dump_path.is_file():
            raise FileNotFoundError(2, 'No such file', str(dump_path))
        print('Dump normalization')
        edges = enumerate(edges_from_dump_by_parts_generator(count=edge_count))
        for i, (relation_uri, start_uri, end_uri, _) in tqdm(edges, unit=' edges', total=edge_count):
            normalize_relation()
            normalize_concept(start_uri)
            normalize_concept(end_uri)

    def insert() -> None:
        """Load dump from CSV and lmdb database into database."""

        def insert_objects_from_edge():
            nonlocal edge_i

            def insert_relation() -> int:
                nonlocal relation_i

                relation_b = relation_in_bytes(relation_uri=relation_uri)
                result_id, = unpack_ints(buffer=txn.get(relation_b, db=relation_db))
                if result_id == relation_i:
                    name = relation_b.decode('utf8')
                    db.execute_sql('insert into relation (name) values (?)', (name, ))
                    relation_i += 1
                return result_id

            def insert_concept(uri: str) -> int:
                nonlocal language_i, label_i, concept_i

                split_uri = uri.split('/', maxsplit=4)

                language_b, label_b = language_and_label_in_bytes(concept_uri=uri)

                language_id, = unpack_ints(buffer=txn.get(language_b, db=language_db))
                if language_id == language_i:
                    name = split_uri[2]
                    db.execute_sql('insert into language (name) values (?)', (name, ))
                    language_i += 1

                label_language_b = label_b + b'/' + language_b
                label_id, = unpack_ints(buffer=txn.get(label_language_b, db=label_db))
                if label_id == label_i:
                    text = split_uri[3]
                    params = (text, language_id)
                    db.execute_sql('insert into label (text, language_id) values (?, ?)', params)
                    label_i += 1

                concept_b = uri.encode('utf8')
                concept_id, = unpack_ints(buffer=txn.get(concept_b, db=concept_db))
                if concept_id == concept_i:
                    sense_label = '' if len(split_uri) == 4 else split_uri[4]
                    params = (label_id, sense_label)
                    db.execute_sql('insert into concept (label_id, sense_label) values (?, ?)', params)
                    concept_i += 1
                return concept_id

            def insert_edge() -> None:
                params = (relation_id, start_id, end_id, edge_etc)
                db.execute_sql('insert into edge (relation_id, start_id, end_id, etc) values (?, ?, ?, ?)', params)

            relation_id = insert_relation()
            start_id = insert_concept(uri=start_uri)
            end_id = insert_concept(uri=end_uri)
            insert_edge()
            edge_i += 1

        print('Dump insertion')
        relation_i, language_i, label_i, concept_i, edge_i = 5 * [1]
        edges = edges_from_dump_by_parts_generator(count=edge_count)
        progress_bar = tqdm(unit=' edges', total=edge_count)
        finished = False
        while not finished:
            edge_count_per_insert = 1000000
            with db.atomic():
                for _ in range(edge_count_per_insert):
                    try:
                        relation_uri, start_uri, end_uri, edge_etc = next(edges)
                    except StopIteration:
                        finished = True
                        break
                    insert_objects_from_edge()
                    progress_bar.update()

    GIB = 1 << 30
    dump_path = Path(dump_path)
    lmdb_db_path = dump_path.parent / f'conceptnet-lmdb-{uuid4()}.db'
    env = lmdb.open(str(lmdb_db_path), map_size=4*GIB, max_dbs=5, sync=False, writemap=False)
    relation_db = env.open_db(b'relation')
    language_db = env.open_db(b'language')
    label_db = env.open_db(b'label')
    concept_db = env.open_db(b'concept')
    try:
        with env.begin(write=True) as txn:
            normalize()
            _open_db(path=db_path)
            insert()
    finally:
        shutil.rmtree(str(lmdb_db_path), ignore_errors=True)
        if delete_dump and dump_path.is_file():
            dump_path.unlink()


def _generate_db_path(db_dir_path: Path) -> Path:
    return db_dir_path / CONCEPTNET_DB_NAME


def prepare_db(
        db_path: PathOrStr,
        dump_download_url: str = CONCEPTNET_DUMP_DOWNLOAD_URL,
        load_dump_edge_count: int = CONCEPTNET_EDGE_COUNT,
        delete_compressed_dump: bool = True,
        delete_dump: bool = True,
):
    """Prepare ConceptNet database.

    This function downloads the compressed ConceptNet dump, extracts it, and loads it into database. First two steps
    are optional, and are executed only if needed.

    Args:
        db_path: Path to the resulting database.
        dump_download_url: Link to compressed ConceptNet dump.
        load_dump_edge_count: Number of edges to load from the beginning of the dump file. Can be useful for testing.
        delete_compressed_dump: Delete compressed dump after extraction.
        delete_dump: Delete dump after loading into database.
    """

    db_path = Path(db_path).expanduser().resolve()
    if db_path.is_dir():
        db_path = _generate_db_path(db_path)
        if db_path.is_file():
            raise FileExistsError(17, "File already exists and it is not a valid database", str(db_path))

    print("Prepare database")
    compressed_dump_path = _get_download_destination_path(db_path.parent, CONCEPTNET_DUMP_DOWNLOAD_URL)
    dump_path = compressed_dump_path.with_suffix('')

    db_path.parent.mkdir(parents=True, exist_ok=True)

    load_dump_to_db_ = partial(
        load_dump_to_db,
        dump_path=dump_path,
        db_path=db_path,
        edge_count=load_dump_edge_count,
        delete_dump=delete_dump,
    )
    extract_compressed_dump_ = partial(
        extract_compressed_dump,
        compressed_dump_path=compressed_dump_path,
        delete_compressed_dump=delete_compressed_dump,
    )
    download_dump_ = partial(
        download_dump,
        url=dump_download_url,
        out_dir_path=db_path.parent,
    )

    try:
        load_dump_to_db_()
    except FileNotFoundError:
        try:
            extract_compressed_dump_()
            load_dump_to_db_()
        except FileNotFoundError:
            download_dump_()
            extract_compressed_dump_()
            load_dump_to_db_()
    finally:
        if delete_compressed_dump and compressed_dump_path.is_file():
            compressed_dump_path.unlink()
        if delete_dump and dump_path.is_file():
            dump_path.unlink()


def download_db(
        url: str = CONCEPTNET_DB_URL,
        db_path: PathOrStr = CONCEPTNET_DB_NAME,
        delete_compressed_db: bool = True
) -> None:
    """Download compressed ConceptNet dump and extract it.

    Args:
        url: Link to compressed ConceptNet database.
        db_path: Path to resulting database.
        delete_compressed_db: Delete compressed database after extraction.
    """

    print("Download compressed database")
    db_path = Path(db_path).expanduser().resolve()
    if db_path.is_dir():
        db_path = _generate_db_path(db_path)
        if db_path.is_file():
            raise FileExistsError(17, "File already exists", str(db_path))
    compressed_db_path = _get_download_destination_path(db_path.parent, url)
    if compressed_db_path.is_file():
        raise FileExistsError(17, "File already exists", str(compressed_db_path))
    downloader = SmartDL(url, str(compressed_db_path))
    downloader.start()
    try:
        with zipfile.ZipFile(str(compressed_db_path), 'r') as zip_f:
            print("Extract compressed database (this can take a few minutes)")
            zip_f.extractall(db_path.parent)
        if db_path.name != CONCEPTNET_DB_NAME:
            Path(db_path.parent / CONCEPTNET_DB_NAME).rename(db_path)
    finally:
        if delete_compressed_db and compressed_db_path.is_file():
            compressed_db_path.unlink()
