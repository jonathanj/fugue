=========================
Fugue: HTTP in two voices
=========================

.. image:: https://travis-ci.org/jonathanj/fugue.svg?branch=master
   :target: https://travis-ci.org/jonathanj/fugue
   :alt: CI status

.. image:: https://codecov.io/github/jonathanj/fugue/coverage.svg?branch=master
   :target: https://codecov.io/github/jonathanj/fugue?branch=master
   :alt: Coverage

.. teaser-begin

Fugue is a Python implementation of the *interceptor* concept as seen in, and
heavily inspired by, `Pedestal`_. It is currently built on `Twisted`_, the
event-driven networking engine for Python, and `Pyrsistent`_ for immutable data
structures.

Briefly, an interceptor is a reusable, composable component responsible for an
individual aspect of the overall behaviour of a web service, such as parsing a
query string or performing content negotiation. Combining interceptors produces
an execution chain that is easily expressed, understood and tested; logic is
kept small and isolated.

.. XXX: Link to docs, when they exist.

.. _Pedestal: http://pedestal.io/
.. _Twisted: https://twistedmatrix.com/
.. _Pyrsistent: https://github.com/tobgu/pyrsistent


------------
Interceptors
------------

Interceptors are the foundation of Fugue, and most of the library is dedicated
to providing interceptors that are useful for building HTTP services.

An interceptor is a pair of unary functions that accept a `context map`_—an
immutable data structure—and must eventually return a context map. One function
(``enter``) is called on the way "in" and another (``leave``) is called on the
way "out". Either function may be omitted and the effect is that the context map
remains unchanged.

Interceptors are combined to produce a particular order of execution, the
"enter" stage is called in order for each interceptor with the—possibly
modified—context map flowing from one to the next. Once all interceptors have
been called, the "leave" stage is called in reverse order for each interceptor
threading the context map—resulting from the "enter" stage—through them;
illustrated below:

::
   
     ┌───────────┐         ┌───────────┐
     │Context map│         │Context map│
     └─────┬─────┘         └─────▲─────┘
           │                     │
   ┌───────┼─────────────────────┼───────┐
   │    ┌──▼──┐               ┌──┴──┐    │
   │    │Enter│               │Leave│    │   Interceptor
   │    └──┬──┘               └──▲──┘    │
   └───────┼─────────────────────┼───────┘
           │                     │
   ┌───────┼─────────────────────┼───────┐
   │    ┌──▼──┐               ┌──┴──┐    │
   │    │Enter│               │Leave│    │   Interceptor
   │    └──┬──┘               └──▲──┘    │
   └───────┼─────────────────────┼───────┘
           │                     │
     ┌─────▼─────┐         ┌─────┴─────┐
     │Context map├ ─ ─ ─ ─ ▶Context map│
     └───────────┘         └───────────┘

Asynchronous results, in the form of a Twisted `Deferred`_, may be returned from
any stage of an interceptor; the effect is that execution of the interceptor
chain is paused until the result becomes available.

Fugue keeps a queue of interceptors that have yet to be called in the context
map itself. Since interceptors are free to modify the context map, this means
they are also able to modify the remaining flow of execution! Terminating the
"enter" stage is a matter of clearing the queue, extending it is a matter of
enqueuing new interceptors; achieved by ``terminate`` and ``enqueue``
respectively.

.. _Deferred: https://twistedmatrix.com/documents/current/core/howto/defer.html

Example
^^^^^^^

A basic interceptor to attach a UUID to some ``uuid`` key on enter:

.. code-block:: python

   Interceptor(
       name='uuid',
       enter=lambda context: context.set(ns('uuid'), uuid4()))

Interceptors executing after this example would find a ``ns('uuid')`` key in the
context map containing a random UUID. In this case ``ns`` is some function
intended to produce namespaced keys to avoid collisions with either internal or
external keys. Fugue provides a basic function to help achieve this in the form
of ``namespace``.

A common pattern is to produce an interceptor from a function and capture the
arguments of the function (via a closure) within the interceptor's enter or
leave functions. For example attaching a database connection to each request:

.. code-block:: python

   def attach_database(uri):
       return Interceptor(
           name='db',
           enter=lambda context: context.set(ns('db'), connect_db(uri)))


--------------
Error handling
--------------

Errors are a natural part of programming, however the normal methods of handling
them are not as useful within the context of an interceptor chain, if only
because they may arise asynchronously.

Instead Fugue traps synchronous and asynchronous errors within interceptors and
attaches them to an ``ERROR`` key in the context map. The "enter" stage is
terminated and the "leave" stage immediately begins, however as long as there is
an ``ERROR`` key in the context map only the ``error`` function of interceptors
along the chain will be invoked.

An error may be handled by returning a context map without the ``ERROR`` key.
When this happens the ``leave`` function of the next interceptor is invoked and
the "leave" stage continues as normal from that point.

If execution ends without the error having been handled it will be be raised
(asynchronously, via a ``Deferred`` `errback`_.

.. _errback: https://twistedmatrix.com/documents/current/core/howto/defer.html#errbacks

Error functions
^^^^^^^^^^^^^^^

An interceptor's ``error`` function is invoked with the context map (devoid of
an ``ERROR`` key, for convenience) and the value of the ``ERROR`` key.

The error function can do one of several things:

1. Return the context map as-is. This is catching the error because there is no
   longer an ``ERROR`` key present and execution will resume normally.
2. Return the context map with the error reattached to the ``ERROR`` key. This
   is reraising the error and the search for an error handler will continue.
3. Raise a new error. This is the error handler encountering a new error trying
   to handle the original error, the search for an error handler will continue
   but for the new error instead.


-----------
Context map
-----------

A context map is passed to each interceptor's ``enter`` and ``leave`` functions.
Below are the basic keys you can expect to find, any key not listed below should
be considered an implementation detail subject to change, either in Fugue itself
or the interceptor responsible for creating the key.

It should be noted that context map returned from each interceptor should be a
transformed version of the one received and *not* a new map. Interceptors may
arbitrarily add new keys that should be preserved.

================ =============
 Key              Description
================ =============
``ERROR``        An object indicating a `Failure`_, in a ``failure`` attribute.
``EXECUTION_ID`` A unique identifier set when the chain is executed.
``QUEUE``        The interceptors left to execute, should be manipulated by
                 ``enqueue``, ``terminate`` and ``terminate_when``.
``TERMINATORS``  Predicates executed after each ``enter`` function, the
                 "enter" stage is terminated if any return a true value.
================ =============


HTTP context map
^^^^^^^^^^^^^^^^

When using Fugue's HTTP request handling the ``REQUEST`` and ``RESPONSE`` keys
will be present, containing information about the request to process and the
response to return.

The request map is attached before the first interceptor is executed, it
describes the incoming HTTP request:

====================== =============
 Key                    Description
====================== =============
``body``               ``file``\-like object containing the body of the request.
``content_type``       ``Content-Type`` header.
``content_length``     ``Content-Length`` header.
``character_encoding`` Content encoding of the ``Content-Type`` header, defaults
                       to ``utf-8``.
``headers``            Map of header names to vectors of header values.
``request_method``     HTTP method.
``uri``                `URL`_ the request is being made to.
====================== =============

The response map is attached by any interceptor in the chain wishing to
influence the HTTP response. If no response map exists when execution completes
an HTTP 404 response is generated.

=========== =============
 Key         Description
=========== =============
``status``  HTTP status code as an ``int``.
``headers`` Optional map of HTTP response headers to include.
``body``    Response body as ``bytes``.
=========== =============

.. XXX: Add keys omitted for brevity.

.. _Failure: https://twistedmatrix.com/documents/current/api/twisted.python.failure.Failure.html
.. _URL: http://hyperlink.readthedocs.io/en/latest/api.html#hyperlink.URL

--------
Adapters
--------

Adapters are the mechanism that bind the external world (such as a web server)
to the internal world of interceptors. If interceptors consume and produce
immutable data via the context map then adapters transform some external
information (such as an HTTP request) to and from that pure data.

This way the majority of the request processing (including application logic) is
unconcerned with the particular web server implementation, the adapter enqueues
the necessary interceptor to transform incoming HTTP requests into data and
outgoing data into HTTP responses.

Fugue provides a Twisted Web adapter in the form of an `IResource`_, the effect
of this adapter is to act as a leaf resource—meaning Twisted performs no child
resource lookups on it—that converts a Twisted Web request into a context map,
executes an interceptor chain, and converts the context map back into something
Twisted Web can respond to the request with.

An adapter has no formal structure since the coupling will depend on what is
being adapted.

.. _IResource: https://twistedmatrix.com/documents/current/api/twisted.web.resource.IResource.html


-------
Example
-------

A `basic HTTP API example`_ that returns a personal greeting based on a route:

.. This should be a literal include, but those are prohibited by Github's
   processors for security reasons.

.. code-block:: python

   from pyrsistent import m
   from fugue.interceptors.http import route
   from fugue.interceptors.http.route import GET
   from fugue.adapters.twisted import twisted_adapter_resource
   
   
   # Define a helper to construct HTTP 200 responses.
   def ok(body):
       return m(status=200, body=body.encode('utf-8'))
   
   # Define the handler behaviour.
   def greet(request):
       name = request['path_params']['name']
       return ok(u'Hello, {}!'.format(name))
   
   # Declare the route.
   interceptor = route.router(
       (u'/greet/:name', GET, greet))
   
   # Create a Twisted Web resource that will execute the interceptor chain.
   resource = twisted_adapter_resource([interceptor])
   
   # Run the script from a Fugue checkout:
   # twistd -n web --resource-script=examples/twisted_greet.py

.. _basic HTTP API example: https://github.com/jonathanj/fugue/blob/master/examples/twisted_greet.py


------------
Installation
------------

.. code-block:: shell

   pip install fugue


------------
Contributing
------------

See `CONTRIBUTING.rst`_.

.. _CONTRIBUTING.rst: https://github.com/jonathanj/fugue/blob/master/CONTRIBUTING.rst
