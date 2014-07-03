#!flask/bin/python
from flask import abort, Flask, jsonify, render_template, request
import happybase
import json
import re
import time

API_VERSION = 'v0.3'

app = Flask(__name__)
connection = happybase.Connection('54.183.87.221')

@app.route('/api/' + API_VERSION + '/brand_metrics', methods = ['GET'])
def get_brand_metrics():
    results = []
    table = connection.table('isura_brand_metrics')
    for key, data in table.scan():
        entry = {}
        entry['brand'] = key
        entry['average_score'] = data['cf1:average_score']
        entry['review_count'] = data['cf1:review_count']
        results.append(entry)
    return jsonify( { 'brand_metrics' : results } )


@app.route('/api/' + API_VERSION + '/brand_metrics/<string:brand>', methods = ['GET'])
def get_brand_metrics_for(brand):
    table = connection.table('isura_brand_metrics')
    row = [r for r in table.scan() if r[0] == brand]
    if not row:
        abort(404)
    return jsonify( { 'brand_metrics' : row[0] } )


@app.route('/api/' + API_VERSION + '/reviews/<string:product>', methods = ['GET'])
def get_review_for(product):
    start = time.time()
    table = connection.table('isura_reviews')
    # Keys are stored in lowercase in HBase for more flexible searching.
    row = table.row(product.lower())
    reviews = []
    if not row:
        abort(404)
    for val in row.itervalues():
        reviews.append(json.loads(val))
    reviews = sorted(reviews, key=lambda k: k['timestamp'])
    reviews = { 'reviews' : reviews }
    reviews['meta'] = { 'count' : len(row), 'responseTime' : time.time() - start }
    return jsonify(reviews)


@app.route('/api/' + API_VERSION + '/reviews/by-keyword/<string:query>', methods = ['GET'])
def get_reviews_by_keyword(query):
    title_table = connection.table('isura_products_by_title')
    keyword_table = connection.table('isura_products_by_keyword')
    product_table = connection.table('isura_reviews_by_product_id')
    query = query.lower()
    keywords = re.split("[^a-z0-9]+", query)
    hits_count = {}
    for w in keywords:
        keyword_row = keyword_table.row(w)
        if keyword_row:
            for product_id in keyword_row.itervalues():
                if product_id in hits:
                    hits_count[product_id] += 1
                else:
                    hits_count[product_id] = 1
    hits_sorted = sorted(hits_count.items(), key=lambda x:x[1])
    hit_products = [h[0] for h in hits_sorted]
    results = {}
    for product_id in hits_products:
        product_row = product_table.row(product_id)
        if product_row:
            results[product_id] = product_row.values()
        else:
            raise Exception("The product_id should be in the table!")
    return jsonify(results)


@app.route('/products/<string:product_id>', methods = ['GET'])
def get_product_reviews(product_id):
    product_table = connection.table('isura_reviews_by_product_id')
    reviews_row = product_table.row(product_id)
    reviews = [] 
    if reviews_row:
        for r in reviews_row.itervalues():
            reviews.append(json.loads(r))
    return render_template('product.html', reviews=reviews)


@app.route('/')
def get_index():
    query = request.args.get('q')
    if not query:
        return render_template('index.html')

    product_table = connection.table('isura_reviews_by_product_id')
    product_ids = get_product_ids(query)
    results = []
    for pid in product_ids:
        row = product_table.row(pid)
        if row:
            reviews = row.values()
            if reviews:
                first = json.loads(reviews[0])
                results.append(first)

    return render_template('index.html', results=results)


def get_product_ids(query):
    query = query.lower()
    keywords = re.split("[^a-z0-9]+", query)
    title_table = connection.table('isura_products_by_title')
    keyword_table = connection.table('isura_products_by_keyword')

    # Try for exact match first.
    title_row = title_table.row(query)
    if title_row:
        return title_row.values()
        #reviews_sorted = sorted(reviews, key=lambda r: r['timestamp'])
    else:
        abort(404)

    hit_count = {}
    for w in keywords:
        keyword_row = keyword_table.row(w)
        if keyword_row:
            for product_id in keyword_row.itervalues():
                if product_id in hit_count:
                    hit_count[product_id] += 1
                else:
                    hit_count[product_id] = 1
    sorted_hits = sorted(hit_count.items(), key=lambda x:x[1])
    sorted_ids = [i[0] for i in sorted_hits] 
    return sorted_ids


if __name__ == '__main__':
    app.run(debug = True)
