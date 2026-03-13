import json
import random
from django.http import HttpResponse, JsonResponse
from django.db import connection


def plaintext(request):
    return HttpResponse('Hello, World!', content_type='text/plain')


def json_view(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        return JsonResponse(data)
    return JsonResponse({'message': 'Hello, World!'})


def user_by_id(request, user_id):
    return JsonResponse({'id': str(user_id)})


def db_single(request):
    id = random.randint(1, 10000)
    with connection.cursor() as c:
        c.execute('SELECT id, randomnumber FROM world WHERE id = %s', [id])
        row = c.fetchone()
    return JsonResponse({'id': row[0], 'randomNumber': row[1]})


def queries(request):
    count = min(max(int(request.GET.get('count', 1)), 1), 500)
    results = []
    for _ in range(count):
        id = random.randint(1, 10000)
        with connection.cursor() as c:
            c.execute('SELECT id, randomnumber FROM world WHERE id = %s', [id])
            row = c.fetchone()
        results.append({'id': row[0], 'randomNumber': row[1]})
    return JsonResponse(results, safe=False)


def template(request):
    items = []
    for _ in range(10):
        id = random.randint(1, 10000)
        with connection.cursor() as c:
            c.execute('SELECT id, randomnumber FROM world WHERE id = %s', [id])
            row = c.fetchone()
        items.append({'id': row[0], 'randomnumber': row[1]})
    rows_html = ''.join(f'<tr><td>{i["id"]}</td><td>{i["randomnumber"]}</td></tr>' for i in items)
    html = f'''<!DOCTYPE html><html><head><title>Benchmark</title></head><body>
<h1>World Database</h1><table><tr><th>ID</th><th>Random Number</th></tr>{rows_html}</table></body></html>'''
    return HttpResponse(html, content_type='text/html')
