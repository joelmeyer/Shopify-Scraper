from flask import Flask, render_template, request, jsonify
import sqlite3
import os
import json

app = Flask(__name__)
DB_PATH = os.path.join(os.path.dirname(__file__), 'data/products.db')  # Adjust if your DB is elsewhere

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
@app.route('/products')
def all_products():
    conn = get_db_connection()
    # Fetch all products for client-side filtering/pagination
    products = conn.execute('SELECT id, title, price, available, vendor, alcohol_type, original_json, url, input_url, published_at, created_at, updated_at, last_seen FROM products ORDER BY last_seen DESC').fetchall()
    product_list = []
    for p in products:
        img_url = None
        try:
            data = json.loads(p['original_json']) if p['original_json'] else {}
            if data.get('images') and len(data['images']) > 0:
                img_url = data['images'][0].get('src')
        except Exception:
            img_url = None
        d = dict(p)
        d['image_url'] = img_url
        product_list.append(d)
    conn.close()
    # No pagination on backend, frontend handles it
    return render_template('products.html', products=product_list)

@app.route('/api/products')
def api_products():
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 500))
    offset = (page - 1) * per_page
    conn = get_db_connection()
    total = conn.execute('SELECT COUNT(*) FROM products').fetchone()[0]
    products = conn.execute('SELECT id, title, price, available, vendor, alcohol_type, original_json, url, input_url, published_at, created_at, updated_at, last_seen FROM products ORDER BY last_seen DESC LIMIT ? OFFSET ?', (per_page, offset)).fetchall()
    product_list = []
    for p in products:
        img_url = None
        try:
            data = json.loads(p['original_json']) if p['original_json'] else {}
            if data.get('images') and len(data['images']) > 0:
                img_url = data['images'][0].get('src')
        except Exception:
            img_url = None
        d = dict(p)
        d['image_url'] = img_url
        product_list.append(d)
    conn.close()
    return jsonify({
        'products': product_list,
        'total': total,
        'page': page,
        'per_page': per_page
    })

if __name__ == '__main__':
    app.run(debug=True)
