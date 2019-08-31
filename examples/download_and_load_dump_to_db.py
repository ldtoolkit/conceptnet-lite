from pathlib import Path

import conceptnet_lite


base_dir_path = Path('~/conceptnet-lite-data')
conceptnet_lite.connect(
    db_path=base_dir_path / 'conceptnet.db',
    dump_dir_path=base_dir_path,
    delete_dump=False,
    delete_compressed_dump=False,
)
