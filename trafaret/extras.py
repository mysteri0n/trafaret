from . import (
    Key, DataError, Any, catch_error, Dict, Bool, Tuple, String,
    Or, Enum, List, _empty, Mapping, Null, Int, Float
)


class KeysSubset(Key):
    """
    From checkers and converters dict must be returned. Some for errors.

    >>> from . import extract_error, Mapping, String
    >>> cmp_pwds = lambda x: {'pwd': x['pwd'] if x.get('pwd') == x.get('pwd1') else DataError('Not equal')}
    >>> d = Dict({KeysSubset('pwd', 'pwd1'): cmp_pwds, 'key1': String})
    >>> sorted(d.check({'pwd': 'a', 'pwd1': 'a', 'key1': 'b'}).keys())
    ['key1', 'pwd']
    >>> extract_error(d.check, {'pwd': 'a', 'pwd1': 'c', 'key1': 'b'})
    {'pwd': 'Not equal'}
    >>> extract_error(d.check, {'pwd': 'a', 'pwd1': None, 'key1': 'b'})
    {'pwd': 'Not equal'}
    >>> get_values = (lambda d, keys: [d[k] for k in keys if k in d])
    >>> join = (lambda d: {'name': ' '.join(get_values(d, ['name', 'last']))})
    >>> Dict({KeysSubset('name', 'last'): join}).check({'name': 'Adam', 'last': 'Smith'})
    {'name': 'Adam Smith'}
    >>> Dict({KeysSubset(): Dict({'a': Any})}).check({'a': 3})
    {'a': 3}
    """

    def __init__(self, *keys):
        self.keys = keys
        self.name = '[%s]' % ', '.join(self.keys)
        self.trafaret = Any()

    def __call__(self, data):
        subdict = dict((k, data.get(k)) for k in self.keys_names() if k in data)
        keys_names = self.keys_names()
        res = catch_error(self.trafaret, subdict)
        if isinstance(res, DataError):
            for k, e in res.error.items():
                yield k, e if isinstance(e, DataError) else DataError(e), keys_names
        else:
            for k, v in res.items():
                yield k, v, keys_names

    def keys_names(self):
        if isinstance(self.trafaret, Dict):
            for key in self.trafaret.keys_names():
                yield key
        for key in self.keys:
            yield key


def get_default_value(key):
    if key.default == _empty:
        return 'N/A'
    elif key.default == '':
        return '""'
    else:
        return key.default


key_fields = ['name', 'default', 'optional', 'value', 'description']

# conversion of key params to the string representation
key_map = {
    'optional': lambda k: True if k.optional else False,
    'default': get_default_value,
}
# inner trafaret names
subtraf_names = []


def join(tr, attrs):
    key_val = []
    for f in attrs:
        if getattr(tr, f) is not None:
            if f == 'regex':
                key_val.append('{}: "{}"'.format(f, getattr(getattr(tr, f), 'pattern')))
            else:
                key_val.append('{}: {}'.format(f, getattr(tr, f)))

    return ', '.join(key_val)


def trafaret_parse(tr, parent=''):
    """
    Convert trafaret to representation for docs.

    :param tr: trafaret object
    :param parent: name of the trafaret hierarchy root

    :return: three values tuple:
        - parent name,
        - brief representation with data types
        - verbose representation with trafarets hierarchy
    """
    if isinstance(tr, Dict):
        trafarets = []
        req_schema = {}
        validation_tables = {}
        is_subtraf = parent.split('.')[-1] in subtraf_names

        for key in tr.keys:
            child_name = '.'.join([parent, key.name])
            key.value, req_value, val_table = trafaret_parse(key.trafaret, child_name)
            if val_table:
                validation_tables.update(val_table)
            trafarets.append([str(key_map[f](key) if f in key_map else getattr(key, f)) for f in key_fields])
            req_schema[key.name] = req_value
        if is_subtraf:
            validation_tables[parent] = trafarets
        return (parent if is_subtraf else req_schema), req_schema, validation_tables

    elif isinstance(tr, String):
        return "String({})".format(join(tr, ('allow_blank', 'regex', 'min_length', 'max_length'))), 'String', {}

    elif any(isinstance(tr, cl) for cl in (Int, Float)):
        num_type = 'Integer' if isinstance(tr, Int) else 'Float'
        return "{}({})".format(num_type, join(tr, ('gt', 'gte', 'lt', 'lte'))), num_type, {}

    elif isinstance(tr, Bool):
        return "Bool", 'Bool', {}

    elif isinstance(tr, Tuple):
        values = []
        req_data = []
        val_tables = {}
        for t in tr.trafarets:
            value, req, val_table = trafaret_parse(t, parent)
            values.append(value)
            req_data.append(req)
            if val_table:
                val_tables.update(val_table)
        return "List([{}], {})".format(', '.join(values), tr.length), req_data, val_tables

    elif isinstance(tr, List):
        value, req_schema, val_table = trafaret_parse(tr.trafaret, parent)
        return "List([{}], {})".format(value, join(tr, ('min_length', 'max_length'))), [req_schema], val_table

    elif isinstance(tr, Any):
        return 'Any', 'Any', {}

    elif isinstance(tr, Or):
        values = []
        req_data = []
        val_tables = {}
        for t in tr.trafarets:
            value, req, val_table = trafaret_parse(t, parent)
            values.append(value)
            req_data.append(str(req))
            if val_table:
                val_tables.update(val_table)

        return "Or({})".format(', '.join(values)), ' or '.join(req_data), val_tables

    elif isinstance(tr, Enum):
        return 'Enum{}'.format(tr.variants), 'Enum{}'.format(tr.variants), {}

    elif isinstance(tr, Null):
        return 'Null', 'Null', {}

    elif isinstance(tr, Mapping):
        key_value, key_req_schema, key_val_table = trafaret_parse(tr.key, parent)
        val_value, val_req_schema, val_val_table = trafaret_parse(tr.value, parent)

        return (
            '{{{0}: {1}}}'.format(key_value, val_value), {'{}'.format(key_req_schema): '{}'.format(val_req_schema)}, {}
        )
    else:
        return '{}'.format(tr), '{}'.format(tr), {}
