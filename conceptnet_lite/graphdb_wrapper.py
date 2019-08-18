from graphdb.SQLiteGraphDB import SQLiteGraphDB


class GraphDb(SQLiteGraphDB):
    def store_relations(self, relations):
        autocommit = self._autocommit
        self._autocommit = False

        i = 1
        for relation in relations:
            self.store_relation(*relation)
            i += 1

        self._autocommit = autocommit
        self.autocommit()

    def relations_between(self, source, target):
        source_id = self._id_of(source)
        target_id = self._id_of(target)
        query_result = self._execute(
            '''select distinct relations.name from relations where src=? and dst=?''',
            (source_id, target_id)
        )
        for x in query_result:
            yield x[0]
