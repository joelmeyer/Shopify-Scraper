from flask import Flask, render_template, request, jsonify, abort, redirect, url_for, flash
import sqlite3
import os
import json

app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = 'your_secret_key'  # Needed for session management and flashing messages
DB_PATH = os.path.join(os.path.dirname(__file__), '../data/products.db')  # Adjusted for new structure
LOG_PATH = os.path.join(os.path.dirname(__file__), '../logs/scraper.log')

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
@app.route('/products')
def all_products():
    conn = get_db_connection()
    products = conn.execute('SELECT id, title, price, available, vendor, alcohol_type, original_json, url, input_url, published_at, created_at, updated_at, last_seen, became_available_at, became_unavailable_at, date_added, ignore_notifications FROM products ORDER BY last_seen DESC').fetchall()
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
    return render_template('products.html', products=product_list)

@app.route('/api/products', methods=['GET'])
def api_products():
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 500))
    offset = (page - 1) * per_page
    conn = get_db_connection()
    total = conn.execute('SELECT COUNT(*) FROM products').fetchone()[0]
    products = conn.execute('SELECT id, title, price, available, vendor, alcohol_type, original_json, url, input_url, published_at, created_at, updated_at, last_seen, became_available_at, became_unavailable_at, date_added, ignore_notifications FROM products ORDER BY last_seen DESC LIMIT ? OFFSET ?', (per_page, offset)).fetchall()
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

@app.route('/api/products/<int:product_id>', methods=['GET'])
def get_product(product_id):
    conn = get_db_connection()
    p = conn.execute('SELECT * FROM products WHERE id = ?', (product_id,)).fetchone()
    conn.close()
    if p is None:
        abort(404)
    d = dict(p)
    try:
        data = json.loads(p['original_json']) if p['original_json'] else {}
        if data.get('images') and len(data['images']) > 0:
            d['image_url'] = data['images'][0].get('src')
        else:
            d['image_url'] = None
    except Exception:
        d['image_url'] = None
    return jsonify(d)

@app.route('/api/products', methods=['POST'])
def create_product():
    data = request.get_json()
    if not data:
        abort(400, 'Missing JSON body')
    fields = ['id', 'handle', 'title', 'available', 'published_at', 'created_at', 'updated_at', 'vendor', 'url', 'price', 'original_json', 'input_url', 'alcohol_type', 'became_available_at', 'became_unavailable_at']
    values = [data.get(f) for f in fields]
    conn = get_db_connection()
    try:
        conn.execute(f"INSERT INTO products ({', '.join(fields)}) VALUES ({', '.join(['?']*len(fields))})", values)
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        abort(409, 'Product already exists')
    conn.close()
    return jsonify({'message': 'Product created'}), 201

@app.route('/api/products/<int:product_id>', methods=['PUT'])
def update_product(product_id):
    data = request.get_json()
    if not data:
        abort(400, 'Missing JSON body')
    fields = ['handle', 'title', 'available', 'published_at', 'created_at', 'updated_at', 'vendor', 'url', 'price', 'original_json', 'input_url', 'alcohol_type', 'became_available_at', 'became_unavailable_at']
    set_clause = ', '.join([f"{f} = ?" for f in fields])
    values = [data.get(f) for f in fields]
    values.append(product_id)
    conn = get_db_connection()
    cur = conn.execute(f"UPDATE products SET {set_clause} WHERE id = ?", values)
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        abort(404, 'Product not found')
    return jsonify({'message': 'Product updated'})

@app.route('/api/products/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    conn = get_db_connection()
    cur = conn.execute('DELETE FROM products WHERE id = ?', (product_id,))
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        abort(404, 'Product not found')
    return jsonify({'message': 'Product deleted'})

@app.route('/api/products/search', methods=['GET'])
def search_products():
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify({'products': [], 'total': 0, 'page': 1, 'per_page': 0})
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 500))
    offset = (page - 1) * per_page
    conn = get_db_connection()
    like = f'%{q}%'
    products = conn.execute('''SELECT id, title, price, available, vendor, alcohol_type, original_json, url, input_url, published_at, created_at, updated_at, last_seen, became_available_at, became_unavailable_at, date_added, ignore_notifications FROM products WHERE title LIKE ? OR vendor LIKE ? OR alcohol_type LIKE ? OR original_json LIKE ? ORDER BY last_seen DESC LIMIT ? OFFSET ?''', (like, like, like, like, per_page, offset)).fetchall()
    total = conn.execute('''SELECT COUNT(*) FROM products WHERE title LIKE ? OR vendor LIKE ? OR alcohol_type LIKE ? OR original_json LIKE ?''', (like, like, like, like)).fetchone()[0]
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

@app.route('/logs')
def view_logs():
    try:
        with open(LOG_PATH, 'r', encoding='utf-8', errors='replace') as f:
            log_content = f.read()[-100_000:]  # Show last 100k chars for performance
    except FileNotFoundError:
        log_content = 'Log file not found.'
    except Exception as e:
        log_content = f'Error reading log file: {e}'
    return render_template('logs.html', log_content=log_content)

@app.route('/api/products/<int:product_id>/ignore', methods=['POST'])
def set_ignore_notifications(product_id):
    data = request.get_json()
    value = int(data.get('ignore_notifications', 0))
    conn = get_db_connection()
    cur = conn.execute('UPDATE products SET ignore_notifications = ? WHERE id = ?', (value, product_id))
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        abort(404, 'Product not found')
    return jsonify({'message': 'ignore_notifications updated', 'id': product_id, 'ignore_notifications': value})

@app.route('/products/<int:product_id>/edit', methods=['POST', 'PUT'])
def edit_product(product_id):
    conn = get_db_connection()
    p = conn.execute('SELECT * FROM products WHERE id = ?', (product_id,)).fetchone()
    if not p:
        conn.close()
        abort(404)
    # Only allow editing a subset of fields for safety
    if request.method in ['POST', 'PUT']:
        if request.is_json:
            data = request.get_json()
            title = data.get('title', p['title'])
            price = data.get('price', p['price'])
            available = int(data.get('available', p['available']))
            vendor = data.get('vendor', p['vendor'])
            alcohol_type = data.get('alcohol_type', p['alcohol_type'])
            ignore_notifications = int(data.get('ignore_notifications', p['ignore_notifications']))
        else:
            title = request.form.get('title', p['title'])
            price = request.form.get('price', p['price'])
            available = int(request.form.get('available', p['available']))
            vendor = request.form.get('vendor', p['vendor'])
            alcohol_type = request.form.get('alcohol_type', p['alcohol_type'])
            ignore_notifications = int(request.form.get('ignore_notifications', p['ignore_notifications']))
        conn.execute('UPDATE products SET title = ?, price = ?, available = ?, vendor = ?, alcohol_type = ?, ignore_notifications = ? WHERE id = ?',
            (title, price, available, vendor, alcohol_type, ignore_notifications, product_id))
        conn.commit()
        conn.close()
        return jsonify({'message': 'Product updated', 'id': product_id})
    conn.close()
    abort(405)

if __name__ == '__main__':
    app.run(debug=True)
