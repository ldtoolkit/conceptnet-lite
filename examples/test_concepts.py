from conceptnet_lite import ConceptNet


cn = ConceptNet(path='conceptnet.db')
relations = list(cn.relations_between('/c/ru/абзац/n', '/c/ru/выступ'))
print("relations_between('/c/ru/абзац/n', '/c/ru/выступ') ==", relations)
antonyms = cn['/c/ru/абзац/n'].antonyms
print("cn['/c/ru/абзац/n'].antonyms ==", [str(antonym) for antonym in antonyms])
