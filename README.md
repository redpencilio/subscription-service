# subscription-service

Microservice turns delta-notifications into emails.

## Adding to docker-compose

First, add the service to your app's `docker-compose.yml`

```
  subscription:
    image: robbe7730/subscription-service:latest
    restart: unless-stopped
    environment:
      EMAIL_SUBJECT: "My subject"
      EMAIL_FROM: "noreply@example.com"
      BASE_URL: "http://example.com"
      MU_SPARQL_ENDPOINT: "http://database:8890/sparql"
    volumes:
      - ./config/subscription/:/config
    links:
      - database:database
      - deliver-email-service:deliver-email-service
```

Then, set up the configuration files:

## Configuration

### Environment variables

- `EMAIL_SUBJECT`: The subject of the email that will be sent.
- `EMAIL_FROM`: The address the email will be sent from.
- `BASE_URL`: The base URL of the application, used for determining graph URLs.
- `MU_SPARQL_ENDPOINT`: The endpoint the SPARQL queries should be sent to.
- `USERFILES_DIR`: The directory the userfiles (information the user still needs to be updated about) will be saved to

### Templates

The `config/subscription/templates` folder will contain the Jinja template
needed to render the email. This template will get three graphs as arguments:

- `inserts` contains all the triples that were added by this delta.
- `deletes` contains all the triples that were deleted by this delta.
- `unchanged` contains all the triples that were not modified by this delta.

Besides that, it also receives some URLs and namespaces for convenience.

In this template, the graphs can be queried by using Pythons slicing syntax to
represent triples. If we want to render every `owl:sameAs` link that was removed
from a given `zitting`, we can do the following:

```jinja2
{% for link in deleted[zitting:OWL.sameAs:] %}
  <a href="{{link}}">link</a>
{% endfor %}
```

### Query files

To get the right data, the service also needs three SPARQL queries under
`config/subscription`.

#### `get_relevant_content.sparql`

This query checks if there is relevant content for a given subject-URL. For
example, if the subject-URL is a `besluit:Zitting`, the content may be every
`besluit:Agendapunt` it handles.

The query should contain one variable `?content` (with zero or more bindings),
the URL of some relevant content. In the query file, the string `SUBJECT_URL`
will be replaced with the actual URL at runtime.

#### `construct_content.sparql`

This query fetches all the relevant triples for a given content URL. The query
should return a CONSTRUCTed graph with all data relevant to the content. In the
query file, the string `CONTENT_URL` will be replaced with the actual URL of the
content.

#### `get_template_subjects.sparql`

To make templating easier, we want some URLs available in the template file. We
do this by querying the content for the URLs we want to use.

This query can return any number of variables, the name of the variable can be
used in the template to represent the URL it was bound to in the query.

Note: If multiple bindings exist, only the first one will be used.

## Database

Subscriptions are stored in the `{BASE_URL}/graphs/subscriptions`
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
