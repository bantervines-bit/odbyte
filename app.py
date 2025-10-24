from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import os
from datetime import datetime
import razorpay
import markdown
import os
from pathlib import Path
import secrets

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///odbyte.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Fix for PostgreSQL URI
if app.config['SQLALCHEMY_DATABASE_URI'].startswith('postgres://'):
    app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace('postgres://', 'postgresql://', 1)

db = SQLAlchemy(app)

# Razorpay Configuration
RAZORPAY_KEY_ID = os.environ.get('RAZORPAY_KEY_ID', 'rzp_test_your_key_id')
RAZORPAY_KEY_SECRET = os.environ.get('RAZORPAY_KEY_SECRET', 'your_key_secret')
razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    plan = db.Column(db.String(20), default='free')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_admin = db.Column(db.Boolean, default=False)  # NEW FIELD
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
    is_premium = db.Column(db.Boolean, default=False)  # NEW FIELD
    premium_status = db.Column(db.String(20), default='none')  # NEW FIELD: 'none', 'pending', 'approved', 'rejected'
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
        
        user = User.query.get(session['user_id'])
        if not user or not user.is_admin:
            flash('Admin access required!', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def generate_bundle_link():
    """Generate a unique random link for bundles"""
    return secrets.token_urlsafe(16)
    
    
@app.route('/')
def index():
    # Get 6 most recent public prompts for homepage
    recent_prompts = Prompt.query.filter_by(visibility='public').order_by(Prompt.created_at.desc()).limit(6).all()
    
    # Get 3 most recent blog posts
    recent_posts = []
    blog_dir = Path('blog_posts')
    
    if blog_dir.exists():
        for file in sorted(blog_dir.glob('*.md'), reverse=True)[:3]:  # Get latest 3
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
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        
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
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
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
    user = User.query.get(session['user_id'])
    if not user:
        session.clear()
        flash('Session expired. Please login again.', 'error')
        return redirect(url_for('login'))
    
    prompts = Prompt.query.filter_by(user_id=user.id).order_by(Prompt.created_at.desc()).all()
    prompt_count = len(prompts)
    
    # Get user's bundles
    bundles = PromptBundle.query.filter_by(user_id=user.id).order_by(PromptBundle.created_at.desc()).limit(5).all()
    bundle_count = PromptBundle.query.filter_by(user_id=user.id).count()
    
    return render_template('dashboard.html', user=user, prompts=prompts, 
                         prompt_count=prompt_count, bundles=bundles, bundle_count=bundle_count)

@app.route('/prompt/new', methods=['GET', 'POST'])
@login_required
def new_prompt():
    user = User.query.get(session['user_id'])
    
    if request.method == 'POST':
        # Get current prompt count FIRST (before any checks)
        current_prompt_count = Prompt.query.filter_by(user_id=user.id).count()
        
        # Check prompt limit based on plan
        if user.plan == 'silver':
            if current_prompt_count >= 10:
                flash('Silver plan limit reached! Upgrade to Diamond for 200 prompts/month.', 'error')
                return redirect(url_for('pricing'))
        elif user.plan == 'diamond':
            if current_prompt_count >= 200:
                flash('Monthly limit reached (200 prompts). Limit resets next month.', 'error')
                return redirect(url_for('dashboard'))
        else:
            # Default to silver limits for any other plan value
            if current_prompt_count >= 10:
                flash('Free plan limit reached! Upgrade to Diamond for 200 prompts/month.', 'error')
                return redirect(url_for('pricing'))
        
        title = request.form.get('title')
        description = request.form.get('description')
        content = request.form.get('content')
        tags = request.form.get('tags')
        
        # Handle custom category
        category = request.form.get('category')
        if category == 'Other':
            category = request.form.get('custom_category', 'Other')
        
        # Handle custom AI model
        ai_model = request.form.get('ai_model')
        if ai_model == 'Other':
            ai_model = request.form.get('custom_ai_model', 'Other')
        
        visibility = request.form.get('visibility', 'public')
        
        # CRITICAL: Silver/Free users can ONLY create public prompts
        if user.plan != 'diamond':
            visibility = 'public'  # Force public for non-diamond users
        
        # Create the prompt
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
        
        # Show success message with count
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
    user = User.query.get(session['user_id'])
    
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
        
        # IMPORTANT: Silver users can ONLY have public prompts
        if user.plan == 'silver':
            prompt.visibility = 'public'  # Force public for silver users
        else:
            prompt.visibility = visibility  # Diamond users can choose
        
        db.session.commit()
        flash('Prompt updated successfully!', 'success')
        return redirect(url_for('dashboard'))
    
    return render_template('edit_prompt.html', prompt=prompt, user=user)

@app.route('/bulk-upload', methods=['GET', 'POST'])
@login_required
def bulk_upload():
    user = User.query.get(session['user_id'])
    
    # Only Diamond users can access bulk upload
    if user.plan != 'diamond':
        flash('Bulk upload is a Diamond feature. Upgrade to access it!', 'error')
        return redirect(url_for('pricing'))
    
    if request.method == 'POST':
        # Get bulk data (could be textarea with JSON/CSV format)
        bulk_data = request.form.get('bulk_data')
        
        # For now, just show coming soon message
        flash('Bulk upload feature coming soon! We\'re working on it.', 'info')
        return redirect(url_for('dashboard'))
    
    return render_template('bulk_upload.html', user=user)

@app.route('/prompt/<int:id>')
def view_prompt(id):
    prompt = Prompt.query.get_or_404(id)
    
    # Check if prompt is private
    if prompt.visibility == 'private':
        if 'user_id' not in session or session['user_id'] != prompt.user_id:
            flash('This prompt is private!', 'error')
            return redirect(url_for('explore'))
    
    # Check if prompt is premium
    if prompt.is_premium and prompt.premium_status == 'approved':
        # Free users cannot view premium prompts
        if 'user_id' not in session:
            flash('Please login to view premium prompts!', 'error')
            return redirect(url_for('login'))
        
        user = User.query.get(session['user_id'])
        if user.plan not in ['diamond', 'premium']:
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
    
    # Start with public prompts
    query = Prompt.query.filter_by(visibility='public')
    
    # Apply filters
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
    
    # Premium filter
    if show_premium == 'true':
        query = query.filter_by(is_premium=True, premium_status='approved')
    
    prompts = query.order_by(Prompt.created_at.desc()).all()
    
    # Check if user is logged in and their plan
    user_plan = None
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
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
    user = User.query.get(session['user_id'])
    if user.plan == 'premium':
        flash('You are already a Premium user!', 'info')
        return redirect(url_for('dashboard'))
    return render_template('upgrade.html', razorpay_key=RAZORPAY_KEY_ID)

@app.route('/create-order', methods=['POST'])
@login_required
def create_order():
    data = request.get_json()
    plan_type = data.get('plan_type', 'monthly')  # 'monthly' or 'annual'
    
    if plan_type == 'annual':
        amount = 3900  # $39 in cents
    else:
        amount = 500  # $5 in cents
    
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
    payment_id = request.form.get('razorpay_payment_id')
    order_id = request.form.get('razorpay_order_id')
    signature = request.form.get('razorpay_signature')
    
    try:
        razorpay_client.utility.verify_payment_signature({
            'razorpay_order_id': order_id,
            'razorpay_payment_id': payment_id,
            'razorpay_signature': signature
        })
        
        user = User.query.get(session['user_id'])
        user.plan = 'premium'
        
        payment = Payment(
            payment_id=payment_id,
            order_id=order_id,
            amount=49900,
            status='success',
            user_id=user.id
        )
        
        db.session.add(payment)
        db.session.commit()
        
        session['user_plan'] = 'premium'
        flash('Payment successful! Welcome to Premium!', 'success')
        return redirect(url_for('payment_success_page'))
    
    except:
        flash('Payment verification failed!', 'error')
        return redirect(url_for('upgrade'))

@app.route('/success')
@login_required
def payment_success_page():
    return render_template('success.html')

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

# Add these new routes to your app.py

# Add this near the top with other imports
from datetime import datetime

# Add these routes BEFORE the "if __name__ == '__main__':" line

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
    # Here you can add logic to save email to database
    # For now, just flash a success message
    flash('Thanks for subscribing! Check your inbox for confirmation.', 'success')
    return redirect(url_for('newsletter'))

@app.route('/blog')
def blog():
    posts = []
    blog_dir = Path('blog_posts')
    
    # If folder doesn't exist, show empty
    if not blog_dir.exists():
        return render_template('blog.html', posts=[])
    
    # Read all .md files
    for file in sorted(blog_dir.glob('*.md'), reverse=True):
        try:
            with open(file, 'r', encoding='utf-8') as f:
                content = f.read()
                
                # Split metadata and content
                if content.startswith('---'):
                    parts = content.split('---', 2)
                    if len(parts) >= 3:
                        metadata_text = parts[1]
                        post_content = parts[2]
                        
                        # Parse metadata
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
    
    # Find post by slug
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
    user = User.query.get(session['user_id'])
    user_bundles = PromptBundle.query.filter_by(user_id=user.id).order_by(PromptBundle.created_at.desc()).all()
    
    bundle_count = len(user_bundles)
    max_bundles = 30 if user.plan == 'diamond' else 3
    
    return render_template('bundles.html', user=user, bundles=user_bundles, 
                         bundle_count=bundle_count, max_bundles=max_bundles)

@app.route('/bundle/new', methods=['GET', 'POST'])
@login_required
def new_bundle():
    user = User.query.get(session['user_id'])
    
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
    user = User.query.get(session['user_id'])
    
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
    author = User.query.get(bundle.user_id)
    
    return render_template('shared_bundle.html', bundle=bundle, prompts=prompts, author=author)

@app.route('/bundle/<int:bundle_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_bundle(bundle_id):
    bundle = PromptBundle.query.get_or_404(bundle_id)
    user = User.query.get(session['user_id'])
    
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
    user = User.query.get(session['user_id'])
    prompt = Prompt.query.get_or_404(id)
    
    # Check if user owns the prompt
    if prompt.user_id != session['user_id']:
        flash('Unauthorized access!', 'error')
        return redirect(url_for('dashboard'))
    
    # Check if user is Diamond
    if user.plan not in ['diamond', 'premium']:
        flash('Only Diamond users can submit premium prompts!', 'error')
        return redirect(url_for('pricing'))
    
    # Check if already submitted
    if prompt.premium_status != 'none':
        flash('This prompt has already been submitted for premium review!', 'info')
        return redirect(url_for('view_prompt', id=id))
    
    # Submit for review
    prompt.premium_status = 'pending'
    db.session.commit()
    
    flash('Prompt submitted for premium review! You\'ll be notified once approved.', 'success')
    return redirect(url_for('view_prompt', id=id))
    @app.route('/admin')
@admin_required
def admin_panel():
    user = User.query.get(session['user_id'])
    
    # Get pending premium prompts
    pending_prompts = Prompt.query.filter_by(premium_status='pending').order_by(Prompt.created_at.desc()).all()
    
    # Get all premium prompts
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
    prompt.visibility = 'public'  # Make it public so it appears in explore
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

# TEMPORARY - REMOVE AFTER USE
@app.route('/make-admin-secret-xyz-2024')
def make_admin_now():
    # CHANGE THIS EMAIL!
    admin_email = 'bantervines@gmail.com'
    
    user = User.query.filter_by(email=admin_email).first()
    
    if user:
        user.is_admin = True
        db.session.commit()
        return f"""
        <html>
        <head>
            <style>
                body {{
                    font-family: Arial;
                    background: #0f172a;
                    color: white;
                    padding: 50px;
                    text-align: center;
                }}
                .success {{ color: #10b981; font-size: 24px; }}
                .warning {{ color: #f59e0b; margin-top: 20px; }}
                a {{ color: #3b82f6; text-decoration: none; }}
            </style>
        </head>
        <body>
            <h1 class="success">✅ Success!</h1>
            <p>{user.name} ({user.email}) is now an admin!</p>
            <p class="warning">⚠️ IMPORTANT: Delete this route from app.py and redeploy NOW!</p>
            <br><br>
            <a href="/dashboard">Go to Dashboard →</a>
        </body>
        </html>
        """
    else:
        return f"""
        <html>
        <head>
            <style>
                body {{
                    font-family: Arial;
                    background: #0f172a;
                    color: white;
                    padding: 50px;
                    text-align: center;
                }}
                .error {{ color: #ef4444; font-size: 24px; }}
            </style>
        </head>
        <body>
            <h1 class="error">❌ User Not Found!</h1>
            <p>No user with email: {admin_email}</p>
            <p>Please:</p>
            <ul style="text-align: left; max-width: 400px; margin: 0 auto;">
                <li>Create an account with this email first</li>
                <li>Make sure the email is spelled correctly</li>
                <li>Log in at least once</li>
            </ul>
            <br><br>
            <a href="/signup">Create Account →</a>
        </body>
        </html>
        """
if __name__ == '__main__':
    app.run(debug=True)
    
