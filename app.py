from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import os
from datetime import datetime
import razorpay
import markdown
from pathlib import Path
import secrets
from supabase import create_client, Client

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///odbyte.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Fix for PostgreSQL URI
if app.config['SQLALCHEMY_DATABASE_URI'].startswith('postgres://'):
    app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace('postgres://', 'postgresql://', 1)

db = SQLAlchemy(app)

# Supabase Configuration
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')

print("=" * 50)
print("🔍 DEBUG: Checking Supabase Credentials")
print(f"SUPABASE_URL exists: {SUPABASE_URL is not None}")
print(f"SUPABASE_KEY exists: {SUPABASE_KEY is not None}")
if SUPABASE_URL:
    print(f"SUPABASE_URL: {SUPABASE_URL[:30]}...")
if SUPABASE_KEY:
    print(f"SUPABASE_KEY: {SUPABASE_KEY[:30]}...")
print("=" * 50)

supabase: Client = None

if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("✅ Supabase connected successfully!")
    except Exception as e:
        print(f"❌ Supabase connection failed: {e}")
else:
    print("⚠️ Supabase credentials not found, using local database")

# Razorpay Configuration
RAZORPAY_KEY_ID = os.environ.get('RAZORPAY_KEY_ID', 'rzp_test_your_key_id')
RAZORPAY_KEY_SECRET = os.environ.get('RAZORPAY_KEY_SECRET', 'your_key_secret')
razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

# Supabase Helper Functions
def get_user_by_email(email):
    """Get user from Supabase by email"""
    if not supabase:
        return None
    try:
        response = supabase.table('users').select('*').eq('email', email).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"Error getting user: {e}")
        return None

def create_user_supabase(name, email, password):
    """Create user in Supabase"""
    if not supabase:
        return None
    try:
        hashed_password = generate_password_hash(password)
        response = supabase.table('users').insert({
            'name': name,
            'email': email,
            'password': hashed_password,
            'plan': 'free',
            'is_admin': False
        }).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"Error creating user: {e}")
        return None

def get_user_by_id(user_id):
    """Get user from Supabase by ID"""
    if not supabase:
        return None
    try:
        response = supabase.table('users').select('*').eq('id', user_id).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"Error getting user by ID: {e}")
        return None

def get_current_user():
    """Get current logged-in user (Supabase or local)"""
    if 'user_id' not in session:
        return None
    
    if supabase:
        user_data = get_user_by_id(session['user_id'])
        if not user_data:
            return None
        
        # Convert dict to User-like object
        class UserProxy:
            def __init__(self, data):
                self.id = data['id']
                self.name = data['name']
                self.email = data['email']
                self.plan = data.get('plan', 'free')
                self.is_admin = data.get('is_admin', False)
                self.created_at = data.get('created_at')
        
        return UserProxy(user_data)
    else:
        return User.query.get(session['user_id'])

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    plan = db.Column(db.String(20), default='free')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_admin = db.Column(db.Boolean, default=False)
    prompts = db.relationship('Prompt', backref='author', lazy=True, cascade='all, delete-orphan')
    favorites = db.relationship('Favorite', backref='user', lazy=True, cascade='all, delete-orphan')

class Prompt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    content = db.Column(db.Text, nullable=False)
    tags = db.Column(db.String(500))
    category = db.Column(db.String(100))
    ai_model = db.Column(db.String(100))
    visibility = db.Column(db.String(20), default='private')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    is_premium = db.Column(db.Boolean, default=False)
    premium_status = db.Column(db.String(20), default='none')
    favorites = db.relationship('Favorite', backref='prompt', lazy=True, cascade='all, delete-orphan')

class Favorite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    prompt_id = db.Column(db.Integer, db.ForeignKey('prompt.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    payment_id = db.Column(db.String(200), nullable=False)
    order_id = db.Column(db.String(200))
    amount = db.Column(db.Integer, nullable=False)
    currency = db.Column(db.String(10), default='INR')
    status = db.Column(db.String(50), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class PromptBundle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    unique_link = db.Column(db.String(100), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    prompt_ids = db.Column(db.Text)

    def get_prompts(self):
        if not self.prompt_ids:
            return []
        ids = [int(id.strip()) for id in self.prompt_ids.split(',') if id.strip()]
        return Prompt.query.filter(Prompt.id.in_(ids)).all()
    
    def add_prompt(self, prompt_id):
        if not self.prompt_ids:
            self.prompt_ids = str(prompt_id)
        else:
            ids = self.prompt_ids.split(',')
            if str(prompt_id) not in ids:
                ids.append(str(prompt_id))
                self.prompt_ids = ','.join(ids)
    
    def remove_prompt(self, prompt_id):
        if self.prompt_ids:
            ids = [id for id in self.prompt_ids.split(',') if id.strip() != str(prompt_id)]
            self.prompt_ids = ','.join(ids)

# Decorators
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page.', 'error')
            return redirect(url_for('login'))
        
        user = get_current_user()
        if not user or not user.is_admin:
            flash('Admin access required!', 'error')
            return redirect(url_for('dashboard'))
        
        return f(*args, **kwargs)
    return decorated_function

@app.context_processor
def inject_user():
    """Make current user available to all templates"""
    if 'user_id' in session:
        current_user = get_current_user()
        return dict(current_user=current_user)
    return dict(current_user=None)

def generate_bundle_link():
    """Generate a unique random link for bundles"""
    return secrets.token_urlsafe(16)

# Routes
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    
    recent_prompts = Prompt.query.filter_by(visibility='public').order_by(Prompt.created_at.desc()).limit(6).all()
    
    recent_posts = []
    blog_dir = Path('blog_posts')
    
    if blog_dir.exists():
        for file in sorted(blog_dir.glob('*.md'), reverse=True)[:3]:
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                    if content.startswith('---'):
                        parts = content.split('---', 2)
                        if len(parts) >= 3:
                            metadata_text = parts[1]
                            
                            metadata = {}
                            for line in metadata_text.strip().split('\n'):
                                if ':' in line:
                                    key, value = line.split(':', 1)
                                    metadata[key.strip()] = value.strip()
                            
                            recent_posts.append({
                                'title': metadata.get('title', 'Untitled'),
                                'slug': metadata.get('slug', ''),
                                'excerpt': metadata.get('excerpt', ''),
                                'category': metadata.get('category', 'General')
                            })
            except Exception as e:
                print(f"Error reading {file}: {e}")
                continue
    
    return render_template('index.html', recent_prompts=recent_prompts, recent_posts=recent_posts)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if supabase:
            existing_user = get_user_by_email(email)
            if existing_user:
                flash('Email already registered!', 'error')
                return redirect(url_for('signup'))
            
            new_user = create_user_supabase(name, email, password)
            if new_user:
                flash('Account created successfully! Please login.', 'success')
                return redirect(url_for('login'))
            else:
                flash('Error creating account. Please try again.', 'error')
                return redirect(url_for('signup'))
        else:
            if User.query.filter_by(email=email).first():
                flash('Email already registered!', 'error')
                return redirect(url_for('signup'))
            
            hashed_password = generate_password_hash(password)
            new_user = User(name=name, email=email, password=hashed_password)
            db.session.add(new_user)
            db.session.commit()
            
            flash('Account created successfully! Please login.', 'success')
            return redirect(url_for('login'))
    
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        if supabase:
            user = get_user_by_email(email)
            if user and check_password_hash(user['password'], password):
                session['user_id'] = user['id']
                session['user_name'] = user['name']
                session['user_plan'] = user['plan']
                flash(f'Welcome back, {user["name"]}!', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Invalid email or password!', 'error')
        else:
            user = User.query.filter_by(email=email).first()
            if user and check_password_hash(user.password, password):
                session['user_id'] = user.id
                session['user_name'] = user.name
                session['user_plan'] = user.plan
                flash(f'Welcome back, {user.name}!', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Invalid email or password!', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully!', 'success')
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    user = get_current_user()
    if not user:
        session.clear()
        flash('Session expired. Please login again.', 'error')
        return redirect(url_for('login'))
    
    prompts = Prompt.query.filter_by(user_id=user.id).order_by(Prompt.created_at.desc()).all()
    prompt_count = len(prompts)
    
    bundles = PromptBundle.query.filter_by(user_id=user.id).order_by(PromptBundle.created_at.desc()).limit(5).all()
    bundle_count = PromptBundle.query.filter_by(user_id=user.id).count()
    
    return render_template('dashboard.html', user=user, prompts=prompts, 
                         prompt_count=prompt_count, bundles=bundles, bundle_count=bundle_count)

@app.route('/prompt/new', methods=['GET', 'POST'])
@login_required
def new_prompt():
    user = get_current_user()
    if not user:
        session.clear()
        flash('Session expired. Please login again.', 'error')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        current_prompt_count = Prompt.query.filter_by(user_id=user.id).count()
        
        if user.plan == 'silver':
            if current_prompt_count >= 10:
                flash('Silver plan limit reached! Upgrade to Diamond for 200 prompts/month.', 'error')
                return redirect(url_for('pricing'))
        elif user.plan == 'diamond':
            if current_prompt_count >= 200:
                flash('Monthly limit reached (200 prompts). Limit resets next month.', 'error')
                return redirect(url_for('dashboard'))
        else:
            if current_prompt_count >= 10:
                flash('Free plan limit reached! Upgrade to Diamond for 200 prompts/month.', 'error')
                return redirect(url_for('pricing'))
        
        title = request.form.get('title')
        description = request.form.get('description')
        content = request.form.get('content')
        tags = request.form.get('tags')
        
        category = request.form.get('category')
        if category == 'Other':
            category = request.form.get('custom_category', 'Other')
        
        ai_model = request.form.get('ai_model')
        if ai_model == 'Other':
            ai_model = request.form.get('custom_ai_model', 'Other')
        
        visibility = request.form.get('visibility', 'public')
        
        if user.plan != 'diamond':
            visibility = 'public'
        
        new_prompt_obj = Prompt(
            title=title,
            description=description,
            content=content,
            tags=tags,
            category=category,
            ai_model=ai_model,
            visibility=visibility,
            user_id=user.id
        )
        
        db.session.add(new_prompt_obj)
        db.session.commit()
        
        new_count = current_prompt_count + 1
        
        if user.plan == 'diamond':
            visibility_text = "private" if visibility == "private" else "public"
            flash(f'Prompt saved as {visibility_text}! ({new_count}/200 Diamond prompts used)', 'success')
        else:
            flash(f'Prompt saved as public! ({new_count}/10 Silver prompts used)', 'success')
        
        return redirect(url_for('dashboard'))
    
    return render_template('new_prompt.html', user=user)

@app.route('/prompt/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_prompt(id):
    prompt = Prompt.query.get_or_404(id)
    user = get_current_user()
    
    if not user:
        session.clear()
        flash('Session expired. Please login again.', 'error')
        return redirect(url_for('login'))
    
    if prompt.user_id != session['user_id']:
        flash('Unauthorized access!', 'error')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        prompt.title = request.form.get('title')
        prompt.description = request.form.get('description')
        prompt.content = request.form.get('content')
        prompt.tags = request.form.get('tags')
        prompt.category = request.form.get('category')
        prompt.ai_model = request.form.get('ai_model')
        
        visibility = request.form.get('visibility', 'public')
        
        if user.plan == 'silver':
            prompt.visibility = 'public'
        else:
            prompt.visibility = visibility
        
        db.session.commit()
        flash('Prompt updated successfully!', 'success')
        return redirect(url_for('dashboard'))
    
    return render_template('edit_prompt.html', prompt=prompt, user=user)

@app.route('/bulk-upload', methods=['GET', 'POST'])
@login_required
def bulk_upload():
    user = get_current_user()
    if not user:
        session.clear()
        flash('Session expired. Please login again.', 'error')
        return redirect(url_for('login'))
    
    if user.plan != 'diamond':
        flash('Bulk upload is a Diamond feature. Upgrade to access it!', 'error')
        return redirect(url_for('pricing'))
    
    if request.method == 'POST':
        bulk_data = request.form.get('bulk_data')
        flash('Bulk upload feature coming soon! We\'re working on it.', 'info')
        return redirect(url_for('dashboard'))
    
    return render_template('bulk_upload.html', user=user)

@app.route('/prompt/<int:id>')
def view_prompt(id):
    prompt = Prompt.query.get_or_404(id)
    
    if prompt.visibility == 'private':
        if 'user_id' not in session or session['user_id'] != prompt.user_id:
            flash('This prompt is private!', 'error')
            return redirect(url_for('explore'))
    
    if prompt.is_premium and prompt.premium_status == 'approved':
        if 'user_id' not in session:
            flash('Please login to view premium prompts!', 'error')
            return redirect(url_for('login'))
        
        user = get_current_user()
        if user and user.plan not in ['diamond', 'premium']:
            flash('Upgrade to Diamond to view premium prompts!', 'error')
            return redirect(url_for('pricing'))
    
    is_favorited = False
    if 'user_id' in session:
        is_favorited = Favorite.query.filter_by(user_id=session['user_id'], prompt_id=id).first() is not None
    
    return render_template('view_prompt.html', prompt=prompt, is_favorited=is_favorited)

@app.route('/prompt/<int:id>/delete', methods=['POST'])
@login_required
def delete_prompt(id):
    prompt = Prompt.query.get_or_404(id)
    
    if prompt.user_id != session['user_id']:
        flash('Unauthorized access!', 'error')
        return redirect(url_for('dashboard'))
    
    db.session.delete(prompt)
    db.session.commit()
    flash('Prompt deleted successfully!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/explore')
def explore():
    search = request.args.get('search', '')
    category = request.args.get('category', '')
    ai_model = request.args.get('ai_model', '')
    show_premium = request.args.get('premium', '')
    
    query = Prompt.query.filter_by(visibility='public')
    
    if search:
        query = query.filter(
            (Prompt.title.contains(search)) | 
            (Prompt.description.contains(search)) |
            (Prompt.tags.contains(search))
        )
    
    if category:
        query = query.filter_by(category=category)
    
    if ai_model:
        query = query.filter_by(ai_model=ai_model)
    
    if show_premium == 'true':
        query = query.filter_by(is_premium=True, premium_status='approved')
    
    prompts = query.order_by(Prompt.created_at.desc()).all()
    
    user_plan = None
    if 'user_id' in session:
        user = get_current_user()
        user_plan = user.plan if user else None
    
    categories = db.session.query(Prompt.category).filter_by(visibility='public').distinct().all()
    ai_models = db.session.query(Prompt.ai_model).filter_by(visibility='public').distinct().all()
    
    return render_template('explore.html', 
                         prompts=prompts, 
                         categories=[c[0] for c in categories if c[0]], 
                         ai_models=[m[0] for m in ai_models if m[0]],
                         user_plan=user_plan)

@app.route('/favorites')
@login_required
def favorites():
    user_favorites = Favorite.query.filter_by(user_id=session['user_id']).all()
    favorite_prompts = [fav.prompt for fav in user_favorites]
    return render_template('favorites.html', prompts=favorite_prompts)

@app.route('/favorite/<int:prompt_id>', methods=['POST'])
@login_required
def toggle_favorite(prompt_id):
    existing = Favorite.query.filter_by(user_id=session['user_id'], prompt_id=prompt_id).first()
    
    if existing:
        db.session.delete(existing)
        db.session.commit()
        return jsonify({'status': 'removed', 'message': 'Removed from favorites'})
    else:
        new_favorite = Favorite(user_id=session['user_id'], prompt_id=prompt_id)
        db.session.add(new_favorite)
        db.session.commit()
        return jsonify({'status': 'added', 'message': 'Added to favorites'})

@app.route('/upgrade')
@login_required
def upgrade():
    user = get_current_user()
    if not user:
        session.clear()
        flash('Session expired. Please login again.', 'error')
        return redirect(url_for('login'))
    
    if user.plan == 'premium':
        flash('You are already a Premium user!', 'info')
        return redirect(url_for('dashboard'))
    return render_template('upgrade.html', razorpay_key=RAZORPAY_KEY_ID)

@app.route('/create-order', methods=['POST'])
@login_required
def create_order():
    data = request.get_json()
    plan_type = data.get('plan_type', 'monthly')
    
    if plan_type == 'annual':
        amount = 3900
    else:
        amount = 500
    
    order_data = {
        'amount': amount,
        'currency': 'USD',
        'payment_capture': 1
    }
    
    order = razorpay_client.order.create(data=order_data)
    
    return jsonify({
        'order_id': order['id'],
        'amount': amount,
        'currency': 'USD',
        'key': RAZORPAY_KEY_ID,
        'plan_type': plan_type
    })

@app.route('/payment-success', methods=['POST'])
@login_required
def payment_success():
    # ... payment verification ...
    
    # ❌ PROBLEM: Payment record mein user_id from session le raha hai
    # Lekin Supabase mein user hai, local DB mein nahi!
    
    payment = Payment(
        payment_id=payment_id,
        order_id=order_id,
        amount=49900,  # ❌ Fixed amount, plan_type se calculate nahi kar raha
        status='success',
        user_id=session['user_id']  # ✅ This is fine
    )
    
    db.session.add(payment)
    db.session.commit()

@app.route('/success')
@login_required
def payment_success_page():
    return render_template('success.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/privacy-policy')
def privacy_policy():
    return render_template('privacy_policy.html')

@app.route('/terms-of-service')
def terms_of_service():
    return render_template('terms_of_service.html')

@app.route('/newsletter')
def newsletter():
    return render_template('newsletter.html')

@app.route('/pricing')
def pricing():
    return render_template('pricing.html')

@app.route('/newsletter/subscribe', methods=['POST'])
def newsletter_subscribe():
    email = request.form.get('email')
    flash('Thanks for subscribing! Check your inbox for confirmation.', 'success')
    return redirect(url_for('newsletter'))

@app.route('/blog')
def blog():
    posts = []
    blog_dir = Path('blog_posts')
    
    if not blog_dir.exists():
        return render_template('blog.html', posts=[])
    
    for file in sorted(blog_dir.glob('*.md'), reverse=True):
        try:
            with open(file, 'r', encoding='utf-8') as f:
                content = f.read()
                
                if content.startswith('---'):
                    parts = content.split('---', 2)
                    if len(parts) >= 3:
                        metadata_text = parts[1]
                        post_content = parts[2]
                        
                        metadata = {}
                        for line in metadata_text.strip().split('\n'):
                            if ':' in line:
                                key, value = line.split(':', 1)
                                metadata[key.strip()] = value.strip()
                        
                        posts.append({
                            'title': metadata.get('title', 'Untitled'),
                            'slug': metadata.get('slug', ''),
                            'date': metadata.get('date', ''),
                            'author': metadata.get('author', 'ODByte Team'),
                            'category': metadata.get('category', 'General'),
                            'excerpt': metadata.get('excerpt', ''),
                            'content': markdown.markdown(post_content, extensions=['fenced_code', 'codehilite'])
                        })
        except Exception as e:
            print(f"Error reading {file}: {e}")
            continue
    
    return render_template('blog.html', posts=posts)

@app.route('/blog/<slug>')
def blog_post(slug):
    blog_dir = Path('blog_posts')
    
    if not blog_dir.exists():
        flash('Blog post not found!', 'error')
        return redirect(url_for('blog'))
    
    for file in blog_dir.glob('*.md'):
        try:
            with open(file, 'r', encoding='utf-8') as f:
                content = f.read()
                
                if content.startswith('---'):
                    parts = content.split('---', 2)
                    if len(parts) >= 3:
                        metadata_text = parts[1]
                        post_content = parts[2]
                        
                        metadata = {}
                        for line in metadata_text.strip().split('\n'):
                            if ':' in line:
                                key, value = line.split(':', 1)
                                metadata[key.strip()] = value.strip()
                        
                        if metadata.get('slug') == slug:
                            post = {
                                'title': metadata.get('title', 'Untitled'),
                                'slug': metadata.get('slug', ''),
                                'date': metadata.get('date', ''),
                                'author': metadata.get('author', 'ODByte Team'),
                                'category': metadata.get('category', 'General'),
                                'excerpt': metadata.get('excerpt', ''),
                                'content': markdown.markdown(post_content, extensions=['fenced_code', 'codehilite'])
                            }
                            return render_template('blog_post_template.html', post=post)
        except Exception as e:
            print(f"Error reading {file}: {e}")
            continue
    
    flash('Blog post not found!', 'error')
    return redirect(url_for('blog'))

# Bundle Routes
@app.route('/bundles')
@login_required
def bundles():
    user = get_current_user()
    if not user:
        session.clear()
        flash('Session expired. Please login again.', 'error')
        return redirect(url_for('login'))
    
    user_bundles = PromptBundle.query.filter_by(user_id=user.id).order_by(PromptBundle.created_at.desc()).all()
    
    bundle_count = len(user_bundles)
    max_bundles = 30 if user.plan == 'diamond' else 3
    
    return render_template('bundles.html', user=user, bundles=user_bundles, 
                         bundle_count=bundle_count, max_bundles=max_bundles)

@app.route('/bundle/new', methods=['GET', 'POST'])
@login_required
def new_bundle():
    user = get_current_user()
    if not user:
        session.clear()
        flash('Session expired. Please login again.', 'error')
        return redirect(url_for('login'))
    
    current_bundle_count = PromptBundle.query.filter_by(user_id=user.id).count()
    max_bundles = 30 if user.plan == 'diamond' else 3
    
    if current_bundle_count >= max_bundles:
        plan_name = "Diamond" if user.plan == 'diamond' else "Free"
        flash(f'{plan_name} plan limit reached! You can create {max_bundles} bundles per month.', 'error')
        return redirect(url_for('bundles'))
    
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        selected_prompts = request.form.getlist('prompts')
        
        new_bundle = PromptBundle(
            title=title,
            description=description,
            unique_link=generate_bundle_link(),
            user_id=user.id,
            prompt_ids=','.join(selected_prompts) if selected_prompts else ''
        )
        
        db.session.add(new_bundle)
        db.session.commit()
        
        flash(f'Bundle created successfully! ({current_bundle_count + 1}/{max_bundles} bundles used)', 'success')
        return redirect(url_for('view_bundle', bundle_id=new_bundle.id))
    
    user_prompts = Prompt.query.filter_by(user_id=user.id).order_by(Prompt.created_at.desc()).all()
    
    return render_template('new_bundle.html', user=user, prompts=user_prompts, 
                         bundle_count=current_bundle_count, max_bundles=max_bundles)

@app.route('/bundle/<int:bundle_id>')
@login_required
def view_bundle(bundle_id):
    bundle = PromptBundle.query.get_or_404(bundle_id)
    user = get_current_user()
    
    if not user:
        session.clear()
        flash('Session expired. Please login again.', 'error')
        return redirect(url_for('login'))
    
    if bundle.user_id != session['user_id']:
        flash('Unauthorized access!', 'error')
        return redirect(url_for('bundles'))
    
    prompts = bundle.get_prompts()
    share_link = url_for('view_shared_bundle', link=bundle.unique_link, _external=True)
    
    return render_template('view_bundle.html', bundle=bundle, prompts=prompts, 
                         user=user, share_link=share_link)

@app.route('/b/<link>')
def view_shared_bundle(link):
    """Public route to view shared bundles"""
    bundle = PromptBundle.query.filter_by(unique_link=link).first_or_404()
    prompts = bundle.get_prompts()
    
    if supabase:
        author_data = get_user_by_id(bundle.user_id)
        if author_data:
            class AuthorProxy:
                def __init__(self, data):
                    self.id = data['id']
                    self.name = data['name']
            author = AuthorProxy(author_data)
        else:
            author = None
    else:
        author = User.query.get(bundle.user_id)
    
    return render_template('shared_bundle.html', bundle=bundle, prompts=prompts, author=author)

@app.route('/bundle/<int:bundle_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_bundle(bundle_id):
    bundle = PromptBundle.query.get_or_404(bundle_id)
    user = get_current_user()
    
    if not user:
        session.clear()
        flash('Session expired. Please login again.', 'error')
        return redirect(url_for('login'))
    
    if bundle.user_id != session['user_id']:
        flash('Unauthorized access!', 'error')
        return redirect(url_for('bundles'))
    
    if request.method == 'POST':
        bundle.title = request.form.get('title')
        bundle.description = request.form.get('description')
        selected_prompts = request.form.getlist('prompts')
        bundle.prompt_ids = ','.join(selected_prompts) if selected_prompts else ''
        
        db.session.commit()
        flash('Bundle updated successfully!', 'success')
        return redirect(url_for('view_bundle', bundle_id=bundle.id))
    
    user_prompts = Prompt.query.filter_by(user_id=user.id).order_by(Prompt.created_at.desc()).all()
    current_prompt_ids = [int(id) for id in bundle.prompt_ids.split(',') if id]
    
    return render_template('edit_bundle.html', bundle=bundle, prompts=user_prompts, 
                         current_prompt_ids=current_prompt_ids, user=user)

@app.route('/bundle/<int:bundle_id>/delete', methods=['POST'])
@login_required
def delete_bundle(bundle_id):
    bundle = PromptBundle.query.get_or_404(bundle_id)
    
    if bundle.user_id != session['user_id']:
        flash('Unauthorized access!', 'error')
        return redirect(url_for('bundles'))
    
    db.session.delete(bundle)
    db.session.commit()
    flash('Bundle deleted successfully!', 'success')
    return redirect(url_for('bundles'))

@app.route('/prompt/<int:id>/submit-premium', methods=['POST'])
@login_required
def submit_premium(id):
    user = get_current_user()
    prompt = Prompt.query.get_or_404(id)
    
    if not user:
        session.clear()
        flash('Session expired. Please login again.', 'error')
        return redirect(url_for('login'))
    
    if prompt.user_id != session['user_id']:
        flash('Unauthorized access!', 'error')
        return redirect(url_for('dashboard'))
    
    if user.plan not in ['diamond', 'premium']:
        flash('Only Diamond users can submit premium prompts!', 'error')
        return redirect(url_for('pricing'))
    
    if prompt.premium_status != 'none':
        flash('This prompt has already been submitted for premium review!', 'info')
        return redirect(url_for('view_prompt', id=id))
    
    prompt.premium_status = 'pending'
    db.session.commit()
    
    flash('Prompt submitted for premium review! You\'ll be notified once approved.', 'success')
    return redirect(url_for('view_prompt', id=id))

@app.route('/admin')
@admin_required
def admin_panel():
    user = get_current_user()
    
    if not user:
        session.clear()
        flash('Session expired. Please login again.', 'error')
        return redirect(url_for('login'))
    
    pending_prompts = Prompt.query.filter_by(premium_status='pending').order_by(Prompt.created_at.desc()).all()
    approved_prompts = Prompt.query.filter_by(premium_status='approved').order_by(Prompt.created_at.desc()).all()
    
    return render_template('admin_panel.html', user=user, 
                         pending_prompts=pending_prompts, 
                         approved_prompts=approved_prompts)

@app.route('/admin/prompt/<int:id>/approve', methods=['POST'])
@admin_required
def approve_premium(id):
    prompt = Prompt.query.get_or_404(id)
    prompt.premium_status = 'approved'
    prompt.is_premium = True
    prompt.visibility = 'public'
    db.session.commit()
    
    flash(f'Premium prompt "{prompt.title}" approved!', 'success')
    return redirect(url_for('admin_panel'))

@app.route('/admin/prompt/<int:id>/reject', methods=['POST'])
@admin_required
def reject_premium(id):
    prompt = Prompt.query.get_or_404(id)
    prompt.premium_status = 'rejected'
    prompt.is_premium = False
    db.session.commit()
    
    flash(f'Premium prompt "{prompt.title}" rejected.', 'info')
    return redirect(url_for('admin_panel'))

@app.route('/admin/prompt/<int:id>/remove-premium', methods=['POST'])
@admin_required
def remove_premium(id):
    prompt = Prompt.query.get_or_404(id)
    prompt.premium_status = 'none'
    prompt.is_premium = False
    db.session.commit()
    
    flash(f'Premium status removed from "{prompt.title}".', 'info')
    return redirect(url_for('admin_panel'))

# Initialize database tables on startup
def init_db():
    with app.app_context():
        try:
            db.create_all()
            print("=" * 50)
            print("✅ Database tables created successfully!")
            print("=" * 50)
        except Exception as e:
            print("=" * 50)
            print(f"❌ Error creating database tables: {e}")
            print("=" * 50)

# Run initialization
init_db()

if __name__ == '__main__':
    app.run(debug=True)
