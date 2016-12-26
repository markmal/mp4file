'''
Created on Dec 6, 2009

@author: napier


Dec 26, 2016: Added population of mvhd, tkhd, mdhd atoms. Made compatible with Python3
@author: Mark Malakanov
'''
import logging
import os
import struct
import datetime
import pytz

from atomsearch import find_path, findall_path

log = logging.getLogger("mp4file")

class EndOFFile(Exception):
    def __init_(self):
        Exception.__init__(self)

def read32(file):
    data = file.read(4)
    if (data is None or len(data) != 4):
        raise EndOFFile()
    return struct.unpack(">I", data)[0]

def read16(file):
    data = file.read(2)
    if (data is None or len(data) != 2):
        raise EndOFFile()
    return struct.unpack(">H", data)[0]

def read8(file):
    data = file.read(1)
    if (data is None or len(data) != 1):
        raise EndOFFile()
    return struct.unpack(">B", data)[0]

def type_to_str(data):
    a = (data >> 0) & 0xff
    b = (data >> 8) & 0xff
    c = (data >> 16) & 0xff
    d = (data >> 24) & 0xff

    return '%c%c%c%c' % (d, c, b, a)

mp4time0 = datetime.datetime(1904,1,1,hour=0, minute=0, second=0, microsecond=0, tzinfo=pytz.utc)

def mp4time_to_datetime(sec):
    global mp4time0
    return mp4time0 + datetime.timedelta(seconds=sec)

# reorders bytes in 32 bit word ABCD to DCBA
def flip32(val):
    log.debug(val)
    new = ((val & 0x000000FF)<<24)+((val & 0xFF000000)>>24)+((val & 0x0000FF00)<<8)+((val & 0x00FF0000)>>8)
    log.debug(new)
    return new

def parse_atom(file):
    try:
        offset = file.tell()
        size = read32(file)
        type = type_to_str(read32(file))
        if (size == 1):
            size = read32(file)
        return create_atom(size, type, offset, file)
    except EndOFFile:
        return None

ATOM_TYPE_MAP = { '\xa9too': 'encoder',
                  '\xa9nam': 'title',
                  '\xa9alb': 'album',
                  '\xa9art': 'artist',
                  '\xa9cmt': 'comment',
                  '\xa9gen': 'genre',
                  'gnre': 'genre',
                  '\xa9day': 'year',
                  'trkn': 'tracknum',
                  'disk': 'disknum',
                  '\xa9wrt': 'composer',
                  'tmpo': 'bpm',
                  'cptr': 'copyright',
                  'cpil': 'compilation',
                  'covr': 'coverart',
                  'rtng': 'rating',
                  '\xa9grp': 'grouping',
                  'pcst': 'podcast',
                  'catg': 'category',
                  'keyw': 'keyword',
                  'purl': 'podcasturl',
                  'egid': 'episodeguid',
                  'desc': 'description',
                  '\xa9lyr': 'lyrics',
                  'tvnn': 'tvnetwork',
                  'tvsh': 'tvshow',
                  'tven': 'tvepisodenum',
                  'tvsn': 'tvseason',
                  'tves': 'tvepisode',
                  'purd': 'purcahsedate',
                  'pgap': 'gapless',
                  'mvhd': 'mvhd',
                  'tkhd': 'tkhd',
                  'mdhd': 'mdhd'
                  }

# There are a lot of atom's with children.  No need to create
# special classes for all of them
ATOM_WITH_CHILDREN = [ 'stik', 'moov', 'trak',
                       'udta', 'ilst', '\xa9too',
                       '\xa9nam', '\xa9alb', '\xa9art',
                       '\xa9cmt', '\xa9gen', 'gnre',
                       '\xa9day', 'trkn', 'disk',
                       '\xa9wrt', 'tmpo', 'cptr',
                       'cpil', 'covr', 'rtng',
                       '\xa9grp', 'pcst', 'catg',
                       'keyw', 'purl', 'egid',
                       'desc', '\xa9lyr', 'tvnn',
                       'tvsh', 'tven', 'tvsn',
                       'tves', 'purd', 'pgap',
                      ]

def create_atom(size, type, offset, file):
    clz = type
    # Possibly remap atom types that aren't valid
    # python variable names
    if type in ATOM_TYPE_MAP:
        clz = ATOM_TYPE_MAP[type]
    if type in ATOM_WITH_CHILDREN:
        return AtomWithChildren(size, type, clz, offset, file)
    try:
        # Try and eval the class into existance
        return eval("%s(size, type, clz, offset, file)" % clz)
    except NameError:
        # Not defined, use generic Atom
        return Atom(size, type, clz, offset, file)

def parse_atoms(file, maxFileOffset):
    atoms = []
    while file.tell() < maxFileOffset:
        atom = parse_atom(file)
        atoms.append(atom)

        # Seek to the end of the atom
        file.seek(atom.offset + atom.size, os.SEEK_SET)

    return atoms

class Atom(object):
    def __init__(self, size, type, name, offset, file):
        self.size = size
        self.type = type
        self.name = name
        self.offset = offset
        self.file = file
        self.children = []
        self.attrs = {}

    def _set_attr(self, key, value):
        self.attrs[key] = value

    def _set_children(self, children):
        # Tell the children who their parents are
        for child in children:
            child.parent = self
        self.children = children

    def get_attribute(self, key):
        return self.attrs[key]

    def get_atoms(self):
        return self.children

    def find(self, path):
        return find_path(self, path)

    def findall(self, path):
        return findall_path(self, path)

class AtomWithChildren(Atom):
    def __init__(self, size, type, name, offset, file):
        Atom.__init__(self, size, type, name, offset, file)
        self._set_children(parse_atoms(file, offset + size))

class ftyp(Atom):
    def __init__(self, size, type, name, offset, file):
        Atom.__init__(self, size, type, name, offset, file)
        self._set_attr('major_version', type_to_str(read32(file)))
        self._set_attr('minor_version', read32(file))

class meta(Atom):
    def __init__(self, size, type, name, offset, file):
        Atom.__init__(self, size, type, name, offset, file)
        # meta has an extra null after the atom header.  consume it here
        read32(file)
        self._set_children(parse_atoms(file, offset + size))

class data(Atom):
    def __init__(self, size, type, name, offset, file):
        Atom.__init__(self, size, type, name, offset, file)
        # Mask off the version field
        self.type = read32(file) & 0xFFFFFF
        data = None
        if self.type == 1:
            data = self.parse_string()
            self._set_attr("data", data)
        elif self.type == 21 or self.type == 0:
            # Another random null padding
            read32(self.file)
            data = read32(self.file)
            self._set_attr("data", data)
        elif self.type == 13 or self.type == 14:
            # Another random null padding
            read32(self.file)
            data = self.file.read(self.size - 16)
            self._set_attr("data", data)
        else:
            print(self.type)

    def parse_string(self):
        # consume extra null?
        read32(self.file)
        howMuch = self.size - 16
        return unicode(self.file.read(howMuch), "utf-8")

class mvhd(Atom):
    def __init__(self, size, type, name, offset, file):
        Atom.__init__(self, size, type, name, offset, file)
        log.debug('mvhd: size:%d, type:%s, name:%s, offset:%d'%(size, type, name, offset))
        assert type == 'mvhd', "requested atom type is not 'mvhd' : %s"%type        
        assert size == 108, "'mvhd' expected size must be 108, requested atom size is %d"%(size)        
        file.seek(offset)
        sz = read32(file)
        assert sz == size, "'mvhd' expected size must be 108, actual atom size is %d"%(sz)        
        tp = type_to_str(read32(file))
        assert tp == 'mvhd', "atom type is not 'mvhd' : %s"%tp        
        vf = read32(file)        
        self._set_attr("version", vf & 0xFF000000)
        self._set_attr("flags",   vf & 0x00FFFFFF)
        self._set_attr("creation_time", mp4time_to_datetime(read32(file)))
        self._set_attr("modification_time", mp4time_to_datetime(read32(file)))
        self._set_attr("time_scale", (read32(file)))
        self._set_attr("duration", (read32(file)))
        ri = read16(file) # integer part of Preferred Rate
        rf = read16(file) # fraction part of Preferred Rate
        pr = float("%d.%d"%(ri,rf))
        self._set_attr("preferred_rate", pr)
        vi = read8(file) # integer part of Preferred Volume
        vf = read8(file) # fraction part of Preferred Volume
        pv = float("%d.%d"%(vi,vf))
        self._set_attr("preferred_volume", pr)
        reserved = read32(file)
        reserved = read32(file)
        reserved = read16(file)
        matrix =  [ read32(file), read32(file), read32(file),
                    read32(file), read32(file), read32(file),
                    read32(file), read32(file), read32(file) ] 
        self._set_attr("matrix", matrix)
        predefines = [ read32(file), read32(file), read32(file),
                       read32(file), read32(file), read32(file) ]
        self._set_attr("next_track_id",read32(file))

        log.debug(self.attrs)
        
class tkhd(Atom):
    def __init__(self, size, type, name, offset, file):
        Atom.__init__(self, size, type, name, offset, file)
        log.debug('tkhd: size:%d, type:%s, name:%s, offset:%d'%(size, type, name, offset))
        assert type == 'tkhd', "requested atom type is not 'tkhd' : %s"%type        
        assert size == 92, "'tkhd' expected size must be 92, requested atom size is %d"%(size)        
        file.seek(offset)
        sz = read32(file)
        assert sz == size, "'tkhd' expected size must be 92, actual atom size is %d"%(sz)        
        tp = type_to_str(read32(file))
        assert tp == 'tkhd', "atom type is not 'tkhd' : %s"%tp        
        vf = read32(file)        
        self._set_attr("version", vf & 0xFF000000)
        self._set_attr("flags",   vf & 0x00FFFFFF)
        self._set_attr("creation_time", mp4time_to_datetime(read32(file)))
        self._set_attr("modification_time", mp4time_to_datetime(read32(file)))
        self._set_attr("track_id",read32(file))
        reserved = read32(file)
        self._set_attr("duration", (read32(file)))
        reserved = read32(file)
        reserved = read32(file)
        self._set_attr("layer",read16(file))
        self._set_attr("alternate_group",read16(file))
        self._set_attr("volume",read16(file))
        reserved = read16(file)
        matrix =  [ read32(file), read32(file), read32(file),
                    read32(file), read32(file), read32(file),
                    read32(file), read32(file), read32(file) ] 
        self._set_attr("matrix", matrix)
        self._set_attr("track_width", (read32(file)))
        self._set_attr("track_height", (read32(file)))
        log.debug(self.attrs)
        
class mdhd(Atom):
    def __init__(self, size, type, name, offset, file):
        Atom.__init__(self, size, type, name, offset, file)
        log.debug('mdhd: size:%d, type:%s, name:%s, offset:%d'%(size, type, name, offset))
        assert type == 'mdhd', "requested atom type is not 'mdhd' : %s"%type        
        assert size == 32, "'mdhd' expected size must be 32, requested atom size is %d"%(size)        
        file.seek(offset)
        sz = read32(file)
        assert sz == size, "'mdhd' expected size must be 92, actual atom size is %d"%(sz)        
        tp = type_to_str(read32(file))
        assert tp == 'mdhd', "atom type is not 'mdhd' : %s"%tp        
        vf = read32(file)        
        self._set_attr("version", vf & 0xFF000000)
        self._set_attr("flags",   vf & 0x00FFFFFF)
        self._set_attr("creation_time", mp4time_to_datetime(read32(file)))
        self._set_attr("modification_time", mp4time_to_datetime(read32(file)))
        self._set_attr("time_scale", (read32(file)))
        self._set_attr("duration", (read32(file)))
        self._set_attr("language",read16(file))
        self._set_attr("quality",read16(file))
        log.debug(self.attrs)
        
        

