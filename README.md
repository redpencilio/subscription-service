# subscription-service

Microservice turns delta-notifications into emails.

## Adding to docker-compose

First, add the service to your app's `docker-compose.yml`

```
subscription:
  image: robbe7730/subscription-service:latest
  restart: unless-stopped
  volumes:
    - ./config/subscription/:/config
  links:
    - database:db
    - deliver-email-service:deliver-email-service
    # - deltanotifier:deltanotifier
```

Then, set up the configuration files:

## Configuration files

### Templates

The `config/subscription/templates` folder will contain the Jinja template
needed to render the email. This template will get three graphs as arguments:

- `inserts` contains all the triples that were added by this delta.
- `deletes` contains all the triples that were deleted by this delta.
- `unchanged` contains all the triples that were not modified by this delta.

Besides that, it also receives some URLs and namespaces for convenience.
(currently it only receives the URLs `agendapunt`, `zitting`, `zitting_notulen`
and `stemming`, but this will be more generic in the future).

In this template, the graphs can be queried by using Pythons slicing syntax to
represent triples. If we want to render every `owl:sameAs` link that was removed
from a given `zitting`, we can do the following:

```jinja2
{% for link in deleted[zitting:OWL.sameAs:] %}
  <a href="{{link}}">link</a>
{% endfor %}
```

## Database

Subscriptions are stored in the `http://lokaalbeslist.be/graphs/subscriptions`
graph. Users are stored as follows:

```ttl
<USER> a schema:Person;
       schema:email "EMAIL";
       ext:hasSubscription <FILTER>. # Can be multiple filters
```

An example of such a filter is:

```ttl
<FILTER> a sh:NodeShape;
         sh:targetClass besluit:Agendapunt;
         sh:or (
           <FILTER-or1>
           <FILTER-or2>
         ).

<FILTER-or1> sh:and (
               <FILTER-or1-and1>
               <FILTER-or1-and2>
             ).

<FILTER-or1-and1> sh:pattern "werken";
                  sh:path terms:title.

<FILTER-or1-and2> sh:pattern "schoolstraat";
                  sh:path terms:title.

<FILTER-or2> sh:path terms:title;
             sh:pattern "politie".
```
