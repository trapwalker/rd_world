
import os
import sys
import shelve
from pprint import pprint as pp
import yaml


if __name__ == '__main__':
    sys.path.append(r'D:\Home\svp\projects\sublayers')
    import sublayers_server.model.registry.classes
    from sublayers_server.model.registry.storage import Registry, Collection
    
    files = sys.argv[1:]
    files += ['agents']

    world_path = r'D:\Home\svp\projects\sublayers\sublayers_server\world'

    reg = Registry(name='registry', path=os.path.join(world_path, 'registry'))
    
    for fname in files:
        print u'# {} #'.format(fname)
        f = shelve.open(fname)
        try:
            for k, v in f.items():
                print u'  ## {} ##'.format(k)
                #pp(yaml.dump(v.resume_dict()))
                print yaml.dump(v.resume_dict(), encoding='utf-8', unicode=True)
        finally:
            f.close()
