from django.conf import settings
from django.shortcuts import render
import time


from elasticsearch import Elasticsearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth
from elasticsearch_dsl import Search
from elasticsearch_dsl.query import Q, FunctionScore, SF
from elasticsearch_dsl.aggs import A, Filters

host = settings.AWS['ES_HOST']
awsauth = AWS4Auth(settings.AWS['ACCESS_KEY'], settings.AWS['SECRET_KEY'], 'us-east-2', 'es')

es = Elasticsearch(
    hosts=[{'host': host, 'port': 443}],
    http_auth=awsauth,
    use_ssl=True,
    verify_certs=True,
    connection_class=RequestsHttpConnection
)


SOURCE_MAP = {
    'bot.unprecedented': {
        'name': '"Unprecedented" bot',
    },
    'bot.outraged': {
        'name': '"Outraged" bot'
    },
    'johnoliver': {
        'name': 'John Oliver',
        'url': 'https://gofccyourself.com'
    },
    'form.battleforthenet': {
        'name': 'Battle for the Net',
        'url': 'https://www.battleforthenet.com/'
    }
}


def index(request):

    s = Search(using=es)

    total = s.count()
    pro_titleii = s.query('match', **{'analysis.titleii': True}).count()
    anti_titleii = s.query('match', **{'analysis.titleii': False}).count()
    unknown_titleii = total - pro_titleii - anti_titleii

    context = {
        'total_comments': s.count(),
        'title_ii': {
            'pro': pro_titleii / total * 100,
            'anti': anti_titleii / total * 100,
            'unknown': unknown_titleii / total * 100
        }
    }
    a = A('terms', field='analysis.source')
    s.aggs.bucket('sources', a)
    response = s.execute()
    context['sources'] = []
    for source in response.aggregations.sources.buckets:
        if source.key == 'unknown':
            continue

        context['sources'].append({
            'key': source.key,
            'count': source.doc_count,
            'name': SOURCE_MAP.get(source.key, {}).get('name'),
            'url': SOURCE_MAP.get(source.key, {}).get('url')
        })

        print(source.key, source.doc_count)
    # context['sources'] = s.aggs['sources']

    return render(request, 'index.html', context)


def browse(request):

    s = Search(using=es)
    description = None

    s.query = FunctionScore(
        query=s.query, functions=[SF('random_score', seed=int(time.time()))]
    )

    if 'source' in request.GET:
        source = request.GET['source']
        s = s.filter('terms', **{'analysis.source': [source]})
        description = SOURCE_MAP.get(source, {}).get('name') or source
    elif 'titleii' in request.GET:
        title_ii = request.GET['titleii']
        if title_ii == 'pro':
            s = s.filter('terms', **{'analysis.titleii': [True]})
            description = "Pro Title II"
        elif title_ii == 'anti':
            description = 'Anti Title II'
            s = s.filter('terms', **{'analysis.titleii': [False]})
        elif title_ii == 'unknown':
            description = 'Uncategorized'
            s = s.exclude('exists', field='analysis.titleii')

    s.aggs.bucket('address', A('terms', field='analysis.fulladdress'))
    s.aggs.bucket('site', A('terms', field='analysis.onsite'))

    s.aggs.bucket('email_confirmation', A('filters', filters={
        'true': {'term': {'emailConfirmation': 'true'}},
        'false': {'term': {'emailConfirmation': 'false'}}
    }))

    # s.aggs.bucket('email_confirmation', A('filters', field='analysis.fulladdress'))

    stats = {
        'Comment Form': {
            'On-site': 0,
            'Off-site': 0
        },
        'Emails': {
            'Unique': 0,
            'Repeated': 0
        },
        'Address': {
            'Full Address': 0,
            'Partial Address': 0,
        },
        'Email Confirmation': {
            'True': 0,
            'False': 0,
            'Missing': 0
        }
    }

    response = s.execute()
    total = s.count()
    for bucket in response.aggregations.address.buckets:
        if bucket.key == 1:
            stats['Address']['Full Address'] = bucket.doc_count
        elif bucket.key == 0:
            stats['Address']['Partial Address'] = bucket.doc_count

    for bucket in response.aggregations.address.buckets:
        if bucket.key == 1:
            stats['Comment Form']['On-site'] = bucket.doc_count
        elif bucket.key == 0:
            stats['Comment Form']['Off-site'] = bucket.doc_count

    # for bucket in response.aggregations.email_confirmation.buckets:
    #     if bucket == 'true':
    #         stats['Email Confirmation']['True'] = response.aggregations.email_confirmation.buckets['true']['doc_count']
    #     elif bucket == 'false':
    #         stats['Email Confirmation']['False'] = response.aggregations.email_confirmation.buckets['false']['doc_count']
    # stats['Email Confirmation']['Missing'] = (
    #     total - stats['Email Confirmation']['True'] - stats['Email Confirmation']['False']
    # )

    context = {
        'description': description,
        'stats': stats,
        'results': response,
        'comment_count': total
    }

    return render(request, 'listing.html', context)
