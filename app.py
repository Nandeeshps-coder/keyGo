from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
import json
import os
import secrets
from datetime import datetime
from urllib.parse import urlparse

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)  # For flash messages

# JSON file to store bookmarks
BOOKMARKS_FILE = 'bookmarks.json'

def load_bookmarks():
    if os.path.exists(BOOKMARKS_FILE):
        with open(BOOKMARKS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_bookmarks(bookmarks):
    with open(BOOKMARKS_FILE, 'w') as f:
        json.dump(bookmarks, f, indent=4)

def validate_url(url):
    """Basic URL validation"""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/add_page')
def add_page():
    return render_template('add.html')

@app.route('/search_page')
def search_page():
    return render_template('search.html')

@app.route('/add', methods=['POST'])
def add_bookmark():
    custom_name = request.form['custom_name']
    url = request.form['url']
    notes = request.form.get('notes', '')
    
    # Add http:// if not present
    if not url.startswith(('http://', 'https://')):
        url = 'http://' + url
        
    # Validate URL
    if not validate_url(url):
        flash('Invalid URL format.', 'error')
        return redirect(url_for('add_page'))
    
    bookmarks = load_bookmarks()
    
    if custom_name in bookmarks:
        flash('Error: Custom name already exists!', 'error')
        return redirect(url_for('add_page'))
    
    # Store as dictionary with metadata
    bookmarks[custom_name] = {
        'url': url,
        'notes': notes,
        'date_added': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'visits': 0
    }
    
    save_bookmarks(bookmarks)
    flash(f'Bookmark "{custom_name}" was added successfully!', 'success')
    return redirect(url_for('add_page'))

@app.route('/search', methods=['GET'])
def search():
    custom_name = request.args.get('search')
    bookmarks = load_bookmarks()
    
    if custom_name in bookmarks:
        # Increment the visit counter
        bookmarks[custom_name]['visits'] = bookmarks[custom_name].get('visits', 0) + 1
        save_bookmarks(bookmarks)
        return redirect(bookmarks[custom_name]['url'])
    
    flash('Bookmark not found!', 'error')
    return redirect(url_for('search_page'))

@app.route('/list_bookmarks')
def list_bookmarks():
    bookmarks = load_bookmarks()
    return jsonify(bookmarks)

@app.route('/delete/<custom_name>', methods=['POST'])
def delete_bookmark(custom_name):
    bookmarks = load_bookmarks()
    if custom_name in bookmarks:
        del bookmarks[custom_name]
        save_bookmarks(bookmarks)
        flash(f'Bookmark "{custom_name}" was deleted successfully!', 'success')
    else:
        flash('Bookmark not found!', 'error')
    return redirect(url_for('search_page'))

@app.route('/edit_page/<custom_name>')
def edit_page(custom_name):
    bookmarks = load_bookmarks()
    if custom_name not in bookmarks:
        flash('Bookmark not found!', 'error')
        return redirect(url_for('search_page'))
    
    bookmark = bookmarks[custom_name]
    return render_template('edit.html', name=custom_name, bookmark=bookmark)

@app.route('/edit/<custom_name>', methods=['POST'])
def edit_bookmark(custom_name):
    bookmarks = load_bookmarks()
    if custom_name not in bookmarks:
        flash('Bookmark not found!', 'error')
        return redirect(url_for('search_page'))
    
    new_name = request.form['custom_name']
    url = request.form['url']
    notes = request.form.get('notes', '')
    
    # Add http:// if not present
    if not url.startswith(('http://', 'https://')):
        url = 'http://' + url
    
    # Validate URL
    if not validate_url(url):
        flash('Invalid URL format.', 'error')
        return redirect(url_for('edit_page', custom_name=custom_name))
    
    # If name changed, check if new name exists
    if new_name != custom_name and new_name in bookmarks:
        flash('Error: Custom name already exists!', 'error')
        return redirect(url_for('edit_page', custom_name=custom_name))
    
    # Update bookmark data
    bookmark_data = bookmarks[custom_name]
    bookmark_data.update({
        'url': url,
        'notes': notes,
        'date_modified': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })
    
    # If name changed, need to delete old and add new
    if new_name != custom_name:
        del bookmarks[custom_name]
        bookmarks[new_name] = bookmark_data
    else:
        bookmarks[custom_name] = bookmark_data
    
    save_bookmarks(bookmarks)
    flash(f'Bookmark updated successfully!', 'success')
    return redirect(url_for('search_page'))

@app.route('/export')
def export_bookmarks():
    bookmarks = load_bookmarks()
    return jsonify(bookmarks)

@app.route('/favicon/<custom_name>')
def get_favicon(custom_name):
    # This is a placeholder - in real implementation you would fetch the favicon
    # Return a default favicon or fetch the site's favicon
    return redirect('/static/favicon.ico')

if __name__ == '__main__':
    app.run(debug=True)