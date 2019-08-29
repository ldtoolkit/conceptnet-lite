from pathlib import Path

from conceptnet_lite import ConceptNet


base_dir_path = Path('~/conceptnet-lite-data')
cn = ConceptNet(
    path=base_dir_path / 'conceptnet.db',
    dump_dir_path=base_dir_path,
    delete_dump=False,
    delete_compressed_dump=False,
)
