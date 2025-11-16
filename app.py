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

# Plan Configuration
PLAN_LIMITS = {
    'free': {
        'name': 'Silver (Free)',
        'prompts': 10,
        'bundles': 3,
        'private_prompts': False,
        'premium_access': False
    },
    'gold': {
        'name': 'Gold',
        'prompts': 200,
        'bundles': 30,
        'private_prompts': True,
        'premium_access': True
    },
    'diamond': {
        'name': 'Diamond',
        'prompts': 1000,
        'bundles': 200,
        'private_prompts': True,
        'premium_access': True
    },
    'custom': {
        'name': 'Custom',
        'prompts': -1,  # Unlimited
        'bundles': -1,  # Unlimited
        'private_prompts': True,
        'premium_access': True
    }
}

# Pricing Configuration (in USD cents)
PRICING = {
    'gold': {
        'monthly': 500,  # $5
        'yearly': 3900   # $39 (save $21)
    },
    'diamond': {
        'monthly': 1900,  # $19
        'yearly': 17900   # $179 (save $49)
    }
}

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

def update_user_plan_supabase(user_id, plan):
    """Update user plan in Supabase"""
    if not supabase:
        return None
    try:
        response = supabase.table('users').update({'plan': plan}).eq('id', user_id).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"Error updating user plan: {e}")
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

def get_plan_limits(plan_name):
    """Get limits for a specific plan"""
    return PLAN_LIMITS.get(plan_name, PLAN_LIMITS['free'])

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
    currency = db.Column(db.String(10), default='USD')
    status = db.Column(db.String(50), nullable=False)
    plan_type = db.Column(db.String(20))  # gold/diamond
    billing_cycle = db.Column(db.String(20))  # monthly/yearly
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
        
        # Check if using Supabase and verify email confirmation
        if supabase and session.get('auth_method') == 'email':
            try:
                user = get_current_user()
                if user:
                    # Additional check: verify email is confirmed in Supabase
                    # Note: This is handled at login, but double-check for security
                    pass
            except Exception as e:
                print(f"Session validation error: {e}")
                session.clear()
                flash('Session expired. Please login again.', 'error')
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
            try:
                # Sign up with Supabase Auth (with email verification)
                auth_response = supabase.auth.sign_up({
                    'email': email,
                    'password': password,
                    'options': {
                        'data': {
                            'full_name': name
                        },
                        'email_redirect_to': url_for('auth_callback', _external=True)
                    }
                })
                
                if auth_response.user:
                    # Check if email verification is required
                    if not auth_response.session:
                        # Email verification required
                        flash('Account created! Please check your email to verify your account.', 'success')
                        return redirect(url_for('verify_email'))
                    else:
                        # Auto-confirmed (shouldn't happen if verification is enabled)
                        # Create user in database
                        existing_user = get_user_by_email(email)
                        if not existing_user:
                            create_user_supabase(name, email, password)
                        
                        flash('Account created successfully! Please login.', 'success')
                        return redirect(url_for('login'))
                else:
                    flash('Error creating account. Please try again.', 'error')
                    return redirect(url_for('signup'))
                    
            except Exception as e:
                print(f"Signup error: {e}")
                if 'already registered' in str(e).lower():
                    flash('Email already registered!', 'error')
                else:
                    flash('Error creating account. Please try again.', 'error')
                return redirect(url_for('signup'))
        else:
            # Local database signup (no Supabase)
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
            try:
                # Sign in with Supabase Auth
                auth_response = supabase.auth.sign_in_with_password({
                    'email': email,
                    'password': password
                })
                
                if auth_response.user:
                    user = auth_response.user
                    
                    # Check if email is verified
                    if not user.email_confirmed_at:
                        flash('Please verify your email before logging in. Check your inbox!', 'warning')
                        return redirect(url_for('verify_email'))
                    
                    # Get or create user in database
                    user_data = get_user_by_email(email)
                    if not user_data:
                        # Create user record if doesn't exist
                        user_data = create_user_supabase(
                            name=user.user_metadata.get('full_name', email.split('@')[0]),
                            email=email,
                            password=generate_password_hash(password)
                        )
                    
                    if user_data:
                        session['user_id'] = user_data['id']
                        session['user_name'] = user_data['name']
                        session['user_plan'] = user_data.get('plan', 'free')
                        session['auth_method'] = 'email'
                        flash(f'Welcome back, {user_data["name"]}!', 'success')
                        return redirect(url_for('dashboard'))
                
                flash('Invalid email or password!', 'error')
                
            except Exception as e:
                print(f"Login error: {e}")
                error_msg = str(e).lower()
                if 'invalid' in error_msg or 'credentials' in error_msg:
                    flash('Invalid email or password!', 'error')
                elif 'email not confirmed' in error_msg:
                    flash('Please verify your email before logging in!', 'warning')
                    return redirect(url_for('verify_email'))
                else:
                    flash('Login failed. Please try again.', 'error')
        else:
            # Local database login
            user = User.query.filter_by(email=email).first()
            if user and check_password_hash(user.password, password):
                session['user_id'] = user.id
                session['user_name'] = user.name
                session['user_plan'] = user.plan
                session['auth_method'] = 'email'
                flash(f'Welcome back, {user.name}!', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Invalid email or password!', 'error')
    
    return render_template('login.html')
    

# Email Verification Page
@app.route('/auth/verify-email')
def verify_email():
    """Show email verification page"""
    return render_template('auth/verify_email.html')


# Resend Verification Email
@app.route('/auth/resend-verification', methods=['POST'])
def resend_verification():
    """Resend verification email"""
    if not supabase:
        return jsonify({'error': 'Service unavailable'}), 503
    
    email = request.form.get('email') or request.json.get('email')
    
    if not email:
        return jsonify({'error': 'Email is required'}), 400
    
    try:
        # Resend verification email via Supabase
        supabase.auth.resend({
            'type': 'signup',
            'email': email,
            'options': {
                'email_redirect_to': url_for('auth_callback', _external=True)
            }
        })
        
        return jsonify({'message': 'Verification email sent! Check your inbox.'}), 200
    except Exception as e:
        print(f"Resend verification error: {e}")
        return jsonify({'error': 'Failed to send verification email'}), 500


# Email Verified Success Page
@app.route('/auth/email-verified')
def email_verified():
    """Show email verified success page"""
    return render_template('auth/email_verified.html')
    
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
    
    plan_limits = get_plan_limits(user.plan)
    
    return render_template('dashboard.html', user=user, prompts=prompts, 
                         prompt_count=prompt_count, bundles=bundles, 
                         bundle_count=bundle_count, plan_limits=plan_limits)

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
        plan_limits = get_plan_limits(user.plan)
        
        # Check prompt limit (custom plan has unlimited: -1)
        if plan_limits['prompts'] != -1 and current_prompt_count >= plan_limits['prompts']:
            if user.plan == 'free':
                flash('Free plan limit reached (10 prompts)! Upgrade to Gold for 200 prompts/month.', 'error')
            elif user.plan == 'gold':
                flash('Gold plan limit reached (200 prompts)! Upgrade to Diamond for 1000 prompts/month.', 'error')
            elif user.plan == 'diamond':
                flash('Diamond plan limit reached (1000 prompts)! Contact us for Custom plan.', 'error')
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
        
        # Only paid plans can create private prompts
        if not plan_limits['private_prompts']:
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
        
        # Dynamic success message based on plan
        if plan_limits['prompts'] == -1:
            flash(f'Prompt saved as {visibility}! (Unlimited prompts)', 'success')
        else:
            flash(f'Prompt saved as {visibility}! ({new_count}/{plan_limits["prompts"]} prompts used)', 'success')
        
        return redirect(url_for('dashboard'))
    
    plan_limits = get_plan_limits(user.plan)
    return render_template('new_prompt.html', user=user, plan_limits=plan_limits)

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
        plan_limits = get_plan_limits(user.plan)
        
        # Only paid plans can have private prompts
        if plan_limits['private_prompts']:
            prompt.visibility = visibility
        else:
            prompt.visibility = 'public'
        
        db.session.commit()
        flash('Prompt updated successfully!', 'success')
        return redirect(url_for('dashboard'))
    
    plan_limits = get_plan_limits(user.plan)
    return render_template('edit_prompt.html', prompt=prompt, user=user, plan_limits=plan_limits)

@app.route('/bulk-upload', methods=['GET', 'POST'])
@login_required
def bulk_upload():
    user = get_current_user()
    if not user:
        session.clear()
        flash('Session expired. Please login again.', 'error')
        return redirect(url_for('login'))
    
    # Bulk upload available for Diamond and Custom plans
    if user.plan not in ['diamond', 'custom']:
        flash('Bulk upload is a Diamond/Custom feature. Upgrade to access it!', 'error')
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
    
    # Check premium access
    if prompt.is_premium and prompt.premium_status == 'approved':
        if 'user_id' not in session:
            flash('Please login to view premium prompts!', 'error')
            return redirect(url_for('login'))
        
        user = get_current_user()
        plan_limits = get_plan_limits(user.plan)
        
        if not plan_limits['premium_access']:
            flash('Upgrade to Gold/Diamond to view premium prompts!', 'error')
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
    has_premium_access = False
    if 'user_id' in session:
        user = get_current_user()
        if user:
            user_plan = user.plan
            plan_limits = get_plan_limits(user.plan)
            has_premium_access = plan_limits['premium_access']
    
    categories = db.session.query(Prompt.category).filter_by(visibility='public').distinct().all()
    ai_models = db.session.query(Prompt.ai_model).filter_by(visibility='public').distinct().all()
    
    return render_template('explore.html', 
                         prompts=prompts, 
                         categories=[c[0] for c in categories if c[0]], 
                         ai_models=[m[0] for m in ai_models if m[0]],
                         user_plan=user_plan,
                         has_premium_access=has_premium_access)

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
    
    if user.plan == 'custom':
        flash('You are already on a Custom plan!', 'info')
        return redirect(url_for('dashboard'))
    
    return render_template('upgrade.html', razorpay_key=RAZORPAY_KEY_ID, pricing=PRICING)

@app.route('/create-order', methods=['POST'])
@login_required
def create_order():
    data = request.get_json()
    plan_type = data.get('plan_type', 'gold')  # gold or diamond
    billing_cycle = data.get('billing_cycle', 'monthly')  # monthly or yearly
    
    # Get amount from pricing config
    if plan_type not in PRICING:
        return jsonify({'error': 'Invalid plan type'}), 400
    
    amount = PRICING[plan_type][billing_cycle]
    
    order_data = {
        'amount': amount,
        'currency': 'USD',
        'payment_capture': 1
    }
    
    try:
        order = razorpay_client.order.create(data=order_data)
        
        return jsonify({
            'order_id': order['id'],
            'amount': amount,
            'currency': 'USD',
            'key': RAZORPAY_KEY_ID,
            'plan_type': plan_type,
            'billing_cycle': billing_cycle
        })
    except Exception as e:
        print(f"Error creating order: {e}")
        return jsonify({'error': 'Failed to create order'}), 500

@app.route('/payment-success', methods=['POST'])
@login_required
def payment_success():
    try:
        data = request.get_json()
        payment_id = data.get('razorpay_payment_id')
        order_id = data.get('razorpay_order_id')
        signature = data.get('razorpay_signature')
        plan_type = data.get('plan_type', 'gold')
        billing_cycle = data.get('billing_cycle', 'monthly')
        
        # Verify payment signature
        params_dict = {
            'razorpay_order_id': order_id,
            'razorpay_payment_id': payment_id,
            'razorpay_signature': signature
        }
        
        razorpay_client.utility.verify_payment_signature(params_dict)
        
        # Get amount from pricing config
        amount = PRICING[plan_type][billing_cycle]
        
        # Save payment record
        payment = Payment(
            payment_id=payment_id,
            order_id=order_id,
            amount=amount,
            status='success',
            plan_type=plan_type,
            billing_cycle=billing_cycle,
            user_id=session['user_id']
        )
        
        db.session.add(payment)
        
        # Update user plan
        user = get_current_user()
        if user:
            if supabase:
                update_user_plan_supabase(user.id, plan_type)
            else:
                user_obj = User.query.get(session['user_id'])
                if user_obj:
                    user_obj.plan = plan_type
            
            db.session.commit()
            session['user_plan'] = plan_type
            
            flash(f'Payment successful! Welcome to {plan_type.capitalize()} plan!', 'success')
            return jsonify({'status': 'success', 'redirect': url_for('payment_success_page')})
        else:
            return jsonify({'error': 'User not found'}), 404
            
    except razorpay.errors.SignatureVerificationError:
        return jsonify({'error': 'Payment verification failed'}), 400
    except Exception as e:
        print(f"Payment error: {e}")
        return jsonify({'error': 'Payment processing failed'}), 500

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
    return render_template('pricing.html', pricing=PRICING, plan_limits=PLAN_LIMITS)

@app.route('/newsletter/subscribe', methods=['POST'])
def newsletter_subscribe():
    email = request.form.get('email')
    flash('Thanks for subscribing! Check your inbox for confirmation.', 'success')
    return redirect(url_for('newsletter'))

# Replace this section in your app.py (around line 840-900)

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
                        
                        # IMPORTANT: Allow HTML in markdown
                        posts.append({
                            'title': metadata.get('title', 'Untitled'),
                            'slug': metadata.get('slug', ''),
                            'date': metadata.get('date', ''),
                            'author': metadata.get('author', 'ODByte Team'),
                            'category': metadata.get('category', 'General'),
                            'excerpt': metadata.get('excerpt', ''),
                            'content': markdown.markdown(
                                post_content, 
                                extensions=[
                                    'fenced_code', 
                                    'codehilite',
                                    'extra'  # This allows HTML
                                ],
                                output_format='html5'
                            )
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
                                # IMPORTANT: Allow HTML in markdown
                                'content': markdown.markdown(
                                    post_content,
                                    extensions=[
                                        'fenced_code',
                                        'codehilite', 
                                        'extra',  # Allows HTML
                                        'nl2br',  # Converts newlines to <br>
                                        'sane_lists'  # Better list handling
                                    ],
                                    output_format='html5',
                                    extension_configs={
                                        'codehilite': {
                                            'css_class': 'highlight',
                                            'linenums': False
                                        }
                                    }
                                )
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
    plan_limits = get_plan_limits(user.plan)
    max_bundles = plan_limits['bundles']
    
    return render_template('bundles.html', user=user, bundles=user_bundles, 
                         bundle_count=bundle_count, max_bundles=max_bundles, plan_limits=plan_limits)

@app.route('/bundle/new', methods=['GET', 'POST'])
@login_required
def new_bundle():
    user = get_current_user()
    if not user:
        session.clear()
        flash('Session expired. Please login again.', 'error')
        return redirect(url_for('login'))
    
    current_bundle_count = PromptBundle.query.filter_by(user_id=user.id).count()
    plan_limits = get_plan_limits(user.plan)
    max_bundles = plan_limits['bundles']
    
    # Check bundle limit (custom plan has unlimited: -1)
    if max_bundles != -1 and current_bundle_count >= max_bundles:
        if user.plan == 'free':
            flash('Free plan limit reached (3 bundles)! Upgrade to Gold for 30 bundles/month.', 'error')
        elif user.plan == 'gold':
            flash('Gold plan limit reached (30 bundles)! Upgrade to Diamond for 200 bundles/month.', 'error')
        elif user.plan == 'diamond':
            flash('Diamond plan limit reached (200 bundles)! Contact us for Custom plan.', 'error')
        return redirect(url_for('pricing'))
    
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
        
        # Dynamic success message
        if max_bundles == -1:
            flash(f'Bundle created successfully! (Unlimited bundles)', 'success')
        else:
            flash(f'Bundle created successfully! ({current_bundle_count + 1}/{max_bundles} bundles used)', 'success')
        
        return redirect(url_for('view_bundle', bundle_id=new_bundle.id))
    
    user_prompts = Prompt.query.filter_by(user_id=user.id).order_by(Prompt.created_at.desc()).all()
    
    return render_template('new_bundle.html', user=user, prompts=user_prompts, 
                         bundle_count=current_bundle_count, max_bundles=max_bundles, plan_limits=plan_limits)

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
    
    plan_limits = get_plan_limits(user.plan)
    
    # Only Gold, Diamond, and Custom users can submit premium prompts
    if not plan_limits['premium_access']:
        flash('Only Gold/Diamond/Custom users can submit premium prompts!', 'error')
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
    
    # Statistics
    total_users = User.query.count() if not supabase else len(supabase.table('users').select('id').execute().data)
    total_prompts = Prompt.query.count()
    total_bundles = PromptBundle.query.count()
    
    # Plan distribution
    plan_stats = {}
    if supabase:
        users_data = supabase.table('users').select('plan').execute().data
        for user_data in users_data:
            plan = user_data.get('plan', 'free')
            plan_stats[plan] = plan_stats.get(plan, 0) + 1
    else:
        for plan in ['free', 'gold', 'diamond', 'custom']:
            plan_stats[plan] = User.query.filter_by(plan=plan).count()
    
    return render_template('admin_panel.html', user=user, 
                         pending_prompts=pending_prompts, 
                         approved_prompts=approved_prompts,
                         total_users=total_users,
                         total_prompts=total_prompts,
                         total_bundles=total_bundles,
                         plan_stats=plan_stats)

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
