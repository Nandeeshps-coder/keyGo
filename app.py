from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, send_from_directory, session
import json
import os
import secrets
from datetime import datetime
from urllib.parse import urlparse
import pymongo
import certifi
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
import json
import re
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)  # For flash messages

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = "Please log in to access this page."
login_manager.login_message_category = "error"

# MongoDB configuration from environment variables
MONGODB_URI = os.getenv("MONGODB_URI")
DB_NAME = os.getenv("DB_NAME", "keygo_bookmarks")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "bookmarks")
USER_COLLECTION = "users"  # Collection for storing user accounts

# Connect to MongoDB
try:
    client = pymongo.MongoClient(
        MONGODB_URI,
        ssl=True,
        tls=True,
        tlsAllowInvalidCertificates=True,
        serverSelectionTimeoutMS=5000,
        connectTimeoutMS=5000,
        tlsCAFile=certifi.where()
    )
    # Ping the server to check connection
    client.admin.command('ping')
    print("Connected to MongoDB successfully!")
    db = client[DB_NAME]
    bookmarks_collection = db[COLLECTION_NAME]
    users_collection = db[USER_COLLECTION]
except Exception as e:
    print(f"Failed to connect to MongoDB: {e}")
    # Create a fallback JSON file for local storage if MongoDB is unavailable
    bookmarks_collection = None
    users_collection = None
    
    def load_bookmarks():
        if os.path.exists('bookmarks.json'):
            with open('bookmarks.json', 'r') as f:
                try:
                    return json.load(f)
                except:
                    return {}
        return {}
        
    def save_bookmark(name, bookmark_data):
        bookmarks = load_bookmarks()
        bookmarks[name] = bookmark_data
        with open('bookmarks.json', 'w') as f:
            json.dump(bookmarks, f, indent=4)
            
    def delete_bookmark(name):
        bookmarks = load_bookmarks()
        if name in bookmarks:
            del bookmarks[name]
            with open('bookmarks.json', 'w') as f:
                json.dump(bookmarks, f, indent=4)
                
    def save_bookmarks(bookmarks):
        with open('bookmarks.json', 'w') as f:
            json.dump(bookmarks, f, indent=4)
else:
    # If MongoDB is working, define these functions to use MongoDB
    def load_bookmarks(user_id=None):
        """Load bookmarks from MongoDB collection, filtered by user_id if provided"""
        bookmarks = {}
        
        # Build query
        query = {}
        if user_id:
            query['user_id'] = user_id
            
        cursor = bookmarks_collection.find(query)
        
        for doc in cursor:
            if '_id' in doc:
                # Convert MongoDB ObjectId to string for JSON serialization
                doc['_id'] = str(doc['_id'])
            
            name = doc.get('name')
            if name:
                # Store bookmarks with the name as key for backward compatibility
                bookmarks[name] = {
                    'url': doc.get('url', ''),
                    'notes': doc.get('notes', ''),
                    'date_added': doc.get('date_added', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
                    'visits': doc.get('visits', 0),
                    'date_modified': doc.get('date_modified', ''),
                    'user_id': doc.get('user_id', '')
                }
        
        return bookmarks
    
    def save_bookmark(name, bookmark_data, user_id=None):
        """Save a single bookmark to MongoDB"""
        # Check if bookmark already exists for this user
        query = {'name': name}
        if user_id:
            query['user_id'] = user_id
            
        existing = bookmarks_collection.find_one(query)
        
        # Add name field to the bookmark data
        bookmark_data['name'] = name
        if user_id:
            bookmark_data['user_id'] = user_id
        
        if existing:
            # Update existing bookmark
            bookmarks_collection.update_one(
                query,
                {'$set': bookmark_data}
            )
        else:
            # Insert new bookmark
            bookmarks_collection.insert_one(bookmark_data)
    
    def delete_bookmark(name, user_id=None):
        """Delete a bookmark from MongoDB"""
        query = {'name': name}
        if user_id:
            query['user_id'] = user_id
            
        bookmarks_collection.delete_one(query)
    
    def save_bookmarks(bookmarks, user_id=None):
        """Bulk save all bookmarks (for backward compatibility)"""
        # Clear existing collection for a clean update
        if user_id:
            bookmarks_collection.delete_many({'user_id': user_id})
        else:
            bookmarks_collection.delete_many({})
        
        # Insert all bookmarks as documents
        for name, data in bookmarks.items():
            doc = data.copy()
            doc['name'] = name
            if user_id:
                doc['user_id'] = user_id
            bookmarks_collection.insert_one(doc)

# User class for Flask-Login
class User(UserMixin):
    def __init__(self, user_id, username, email):
        self.id = user_id
        self.username = username
        self.email = email

@login_manager.user_loader
def load_user(user_id):
    if users_collection:
        user_data = users_collection.find_one({"_id": user_id})
        if user_data:
            return User(user_data["_id"], user_data["username"], user_data["email"])
    return None

def validate_url(url):
    """Basic URL validation"""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

def is_valid_password(password):
    """Check if password meets requirements"""
    # At least 8 characters, at least one letter and one number
    if len(password) < 8:
        return False
    if not re.search(r'[A-Za-z]', password):
        return False
    if not re.search(r'\d', password):
        return False
    return True

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        if not email or not password:
            flash('Please enter both email and password', 'error')
            return render_template('login.html')
        
        try:
            if users_collection:
                user_data = users_collection.find_one({'email': email})
                
                if user_data and check_password_hash(user_data['password'], password):
                    user = User(user_data['_id'], user_data['username'], user_data['email'])
                    login_user(user)
                    next_page = request.args.get('next', '/')
                    flash('Login successful!', 'success')
                    return redirect(next_page)
                else:
                    flash('Invalid email or password', 'error')
            else:
                flash('User authentication unavailable', 'error')
        except Exception as e:
            print(f"Login error: {e}")
            flash('Error during login', 'error')
            
        return render_template('login.html')
    
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        # Validation
        if not (username and email and password and confirm_password):
            flash('All fields are required', 'error')
            return render_template('signup.html')
            
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('signup.html')
            
        if not is_valid_password(password):
            flash('Password must be at least 8 characters with at least one letter and one number', 'error')
            return render_template('signup.html')
            
        try:
            if users_collection:
                # Check if username or email already exists
                if users_collection.find_one({'username': username}):
                    flash('Username already exists', 'error')
                    return render_template('signup.html')
                    
                if users_collection.find_one({'email': email}):
                    flash('Email already registered', 'error')
                    return render_template('signup.html')
                    
                # Create user
                user_id = str(secrets.token_hex(16))
                hashed_password = generate_password_hash(password)
                
                user_data = {
                    '_id': user_id,
                    'username': username,
                    'email': email,
                    'password': hashed_password,
                    'date_joined': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                
                users_collection.insert_one(user_data)
                
                # Log the user in
                user = User(user_id, username, email)
                login_user(user)
                
                flash('Account created successfully!', 'success')
                return redirect('/')
            else:
                flash('User registration unavailable', 'error')
        except Exception as e:
            print(f"Registration error: {e}")
            flash('Error during registration', 'error')
            
        return render_template('signup.html')
    
    return render_template('signup.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out', 'success')
    return redirect(url_for('login'))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/add_page')
@login_required
def add_page():
    return render_template('add.html')

@app.route('/shortcuts')
@login_required
def shortcuts():
    return render_template('shortcuts.html')

@app.route('/search_page')
def search_page():
    return redirect(url_for('shortcuts'))

@app.route('/add', methods=['POST'])
@login_required
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
    
    try:
        if bookmarks_collection:
            # Check if bookmark name already exists for this user
            existing = bookmarks_collection.find_one({
                'name': custom_name,
                'user_id': current_user.id
            })
            
            if existing:
                flash('Error: Custom name already exists!', 'error')
                return redirect(url_for('add_page'))
            
            # Create bookmark document
            bookmark_data = {
                'name': custom_name,
                'url': url,
                'notes': notes,
                'date_added': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'visits': 0,
                'user_id': current_user.id
            }
            
            # Save to MongoDB
            bookmarks_collection.insert_one(bookmark_data)
        else:
            # Using JSON storage
            bookmarks = load_bookmarks()
            if custom_name in bookmarks:
                flash('Error: Custom name already exists!', 'error')
                return redirect(url_for('add_page'))
                
            bookmark_data = {
                'url': url,
                'notes': notes,
                'date_added': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'visits': 0,
                'user_id': current_user.id if hasattr(current_user, 'id') else None
            }
            save_bookmark(custom_name, bookmark_data)
        
        flash(f'Bookmark "{custom_name}" was added successfully!', 'success')
    except Exception as e:
        print(f"MongoDB error: {e}")
        # Fallback to JSON file
        try:
            # Make bookmark data compatible with JSON storage
            bookmark_data = {
                'url': url,
                'notes': notes,
                'date_added': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'visits': 0,
                'user_id': current_user.id if hasattr(current_user, 'id') else None
            }
            save_bookmark(custom_name, bookmark_data)
            flash(f'Bookmark "{custom_name}" was added successfully (using local storage)!', 'success')
        except Exception as e:
            print(f"Fallback error: {e}")
            flash('Error saving bookmark!', 'error')
    
    return redirect(url_for('add_page'))

@app.route('/search', methods=['GET'])
def search():
    custom_name = request.args.get('search')
    
    try:
        if bookmarks_collection:
            # Create query based on authentication status
            query = {'name': custom_name}
            if current_user.is_authenticated:
                query['user_id'] = current_user.id
            
            # Find bookmark in MongoDB
            bookmark = bookmarks_collection.find_one(query)
            
            if bookmark:
                # Increment the visit counter
                visits = bookmark.get('visits', 0) + 1
                bookmarks_collection.update_one(
                    query,
                    {'$set': {'visits': visits}}
                )
                return redirect(bookmark['url'])
        
        # Check in local storage as fallback
        bookmarks = load_bookmarks(
            current_user.id if current_user.is_authenticated else None
        )
        if custom_name in bookmarks:
            url = bookmarks[custom_name]['url']
            # Update visit count
            bookmarks[custom_name]['visits'] = bookmarks[custom_name].get('visits', 0) + 1
            save_bookmarks(bookmarks)
            return redirect(url)
            
        flash('Bookmark not found!', 'error')
    except Exception as e:
        print(f"Search error: {e}")
        # Fallback to JSON
        bookmarks = load_bookmarks()
        if custom_name in bookmarks:
            url = bookmarks[custom_name]['url']
            # Update visit count
            bookmarks[custom_name]['visits'] = bookmarks[custom_name].get('visits', 0) + 1
            save_bookmarks(bookmarks)
            return redirect(url)
            
        flash('Error searching bookmarks!', 'error')
    
    return redirect(url_for('index'))

@app.route('/list_bookmarks')
@login_required
def list_bookmarks():
    try:
        if current_user.is_authenticated:
            bookmarks = load_bookmarks(current_user.id)
        else:
            bookmarks = load_bookmarks()
        return jsonify(bookmarks)
    except Exception as e:
        print(f"Error listing bookmarks: {e}")
        # Return empty list if error occurs
        return jsonify({})

@app.route('/delete/<custom_name>', methods=['POST'])
@login_required
def delete_bookmark_route(custom_name):
    try:
        if bookmarks_collection:
            # Check if bookmark exists
            query = {'name': custom_name}
            if current_user.is_authenticated:
                query['user_id'] = current_user.id
                
            bookmark = bookmarks_collection.find_one(query)
            
            if bookmark:
                # Delete from MongoDB
                bookmarks_collection.delete_one(query)
                flash(f'Bookmark "{custom_name}" was deleted successfully!', 'success')
            else:
                # Try local storage
                delete_bookmark(custom_name, 
                    current_user.id if current_user.is_authenticated else None
                )
                flash(f'Bookmark "{custom_name}" was deleted successfully!', 'success')
        else:
            # Use JSON storage
            delete_bookmark(custom_name)
            flash(f'Bookmark "{custom_name}" was deleted successfully!', 'success')
    except Exception as e:
        print(f"Error deleting bookmark: {e}")
        # Try fallback to JSON file
        try:
            delete_bookmark(custom_name)
            flash(f'Bookmark "{custom_name}" was deleted successfully!', 'success')
        except:
            flash('Error deleting bookmark!', 'error')
    
    return redirect(url_for('shortcuts'))

@app.route('/edit_page/<custom_name>')
@login_required
def edit_page(custom_name):
    try:
        if bookmarks_collection and current_user.is_authenticated:
            # Find bookmark in MongoDB
            bookmark_doc = bookmarks_collection.find_one({
                'name': custom_name,
                'user_id': current_user.id
            })
            
            if bookmark_doc:
                # Format bookmark in expected structure
                bookmark = {
                    'url': bookmark_doc.get('url', ''),
                    'notes': bookmark_doc.get('notes', ''),
                    'date_added': bookmark_doc.get('date_added', ''),
                    'visits': bookmark_doc.get('visits', 0)
                }
                
                return render_template('edit.html', name=custom_name, bookmark=bookmark)
        
        # Try fallback to JSON storage
        bookmarks = load_bookmarks(
            current_user.id if current_user.is_authenticated else None
        )
        if custom_name in bookmarks:
            return render_template('edit.html', name=custom_name, bookmark=bookmarks[custom_name])
        
        flash('Bookmark not found!', 'error')
        return redirect(url_for('shortcuts'))
    except Exception as e:
        print(f"Edit page error: {e}")
        # Fallback to JSON
        bookmarks = load_bookmarks()
        if custom_name in bookmarks:
            return render_template('edit.html', name=custom_name, bookmark=bookmarks[custom_name])
        
        flash('Error accessing bookmark!', 'error')
        return redirect(url_for('shortcuts'))

@app.route('/edit/<custom_name>', methods=['POST'])
@login_required
def edit_bookmark(custom_name):
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
    
    try:
        if bookmarks_collection and current_user.is_authenticated:
            # Check if the bookmark exists
            existing = bookmarks_collection.find_one({
                'name': custom_name,
                'user_id': current_user.id
            })
            
            if existing:
                # If name changed, check if new name exists
                if new_name != custom_name:
                    name_exists = bookmarks_collection.find_one({
                        'name': new_name,
                        'user_id': current_user.id
                    })
                    if name_exists:
                        flash('Error: Custom name already exists!', 'error')
                        return redirect(url_for('edit_page', custom_name=custom_name))
                
                # Update bookmark data
                if new_name != custom_name:
                    # Delete old document and create new one with new name
                    bookmarks_collection.delete_one({
                        'name': custom_name,
                        'user_id': current_user.id
                    })
                    
                    bookmark_data = {
                        'name': new_name,
                        'url': url,
                        'notes': notes,
                        'date_added': existing.get('date_added', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
                        'visits': existing.get('visits', 0),
                        'date_modified': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'user_id': current_user.id
                    }
                    
                    bookmarks_collection.insert_one(bookmark_data)
                else:
                    # Update existing document
                    bookmarks_collection.update_one(
                        {'name': custom_name, 'user_id': current_user.id},
                        {'$set': {
                            'url': url,
                            'notes': notes,
                            'date_modified': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        }}
                    )
                
                flash(f'Bookmark updated successfully!', 'success')
                return redirect(url_for('shortcuts'))
        
        # Check in JSON fallback
        bookmarks = load_bookmarks(
            current_user.id if current_user.is_authenticated else None
        )
        if custom_name in bookmarks:
            # Check if new name exists
            if new_name != custom_name and new_name in bookmarks:
                flash('Error: Custom name already exists!', 'error')
                return redirect(url_for('edit_page', custom_name=custom_name))
                
            # Handle edit in JSON file
            old_data = bookmarks[custom_name]
            del bookmarks[custom_name]
            bookmarks[new_name] = {
                'url': url,
                'notes': notes,
                'date_added': old_data.get('date_added', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
                'visits': old_data.get('visits', 0),
                'date_modified': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'user_id': current_user.id if current_user.is_authenticated else None
            }
            save_bookmarks(bookmarks)
            flash(f'Bookmark updated successfully!', 'success')
            return redirect(url_for('shortcuts'))
        
        flash('Bookmark not found!', 'error')
    except Exception as e:
        print(f"Edit error: {e}")
        # Try using JSON fallback
        try:
            bookmarks = load_bookmarks()
            if custom_name in bookmarks:
                old_data = bookmarks[custom_name]
                del bookmarks[custom_name]
                bookmarks[new_name] = {
                    'url': url,
                    'notes': notes,
                    'date_added': old_data.get('date_added', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
                    'visits': old_data.get('visits', 0),
                    'date_modified': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'user_id': current_user.id if current_user.is_authenticated else None
                }
                save_bookmarks(bookmarks)
                flash(f'Bookmark updated successfully (using local storage)!', 'success')
            else:
                flash('Error updating bookmark!', 'error')
        except:
            flash('Error updating bookmark!', 'error')
    
    return redirect(url_for('shortcuts'))

@app.route('/export')
@login_required
def export_bookmarks():
    try:
        if bookmarks_collection and current_user.is_authenticated:
            cursor = bookmarks_collection.find({'user_id': current_user.id})
            bookmarks_list = list(cursor)
            
            # Convert ObjectId to string for JSON serialization
            for doc in bookmarks_list:
                if '_id' in doc:
                    doc['_id'] = str(doc['_id'])
            
            return jsonify(bookmarks_list)
    except Exception as e:
        print(f"Export error: {e}")
    
    # Fallback to JSON
    bookmarks = load_bookmarks(
        current_user.id if current_user.is_authenticated else None
    )
    return jsonify(bookmarks)

# Create a static folder if it doesn't exist
@app.route('/static/<path:filename>')
def static_files(filename):
    static_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
    if not os.path.exists(static_folder):
        os.makedirs(static_folder)
    return send_from_directory(static_folder, filename)

@app.route('/favicon/<custom_name>')
def get_favicon(custom_name):
    # This is a placeholder - returning a static favicon
    return redirect('/static/favicon.ico')

if __name__ == '__main__':
    app.run(debug=True)