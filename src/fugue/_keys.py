from fugue.util import namespace


_ns = namespace('fugue')
REQUEST = _ns('request')
RESPONSE = _ns('response')
ROUTE = _ns('route')
EXECUTION_ID = _ns('execution_id')
QUEUE = _ns('queue')
STACK = _ns('stack')
ERROR = _ns('error')
SUPPRESSED = _ns('suppressed')
TERMINATORS = _ns('terminators')
