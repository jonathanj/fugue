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
