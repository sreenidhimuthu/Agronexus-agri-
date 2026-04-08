from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import os

# Import from models.py
from models import db, User, Product, Cart, Order, OrderItem, Review, Message, Notification

app = Flask(__name__)

# Configuration
app.config['SECRET_KEY'] = 'your-secret-key-change-this-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///agronexus.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Initialize extensions
db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Check if Pillow is available
try:
    from PIL import Image
    PILLOW_AVAILABLE = True
    print("✓ Pillow is available - image uploads enabled")
except ImportError:
    PILLOW_AVAILABLE = False
    print("⚠ Pillow not installed - using default images for uploads")

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ==================== MAIN ROUTES ====================

@app.route('/')
def index():
    featured_products = Product.query.filter_by(available=True).order_by(Product.created_at.desc()).limit(8).all()
    farmers = User.query.filter_by(user_type='farmer').limit(6).all()
    return render_template('index.html', featured_products=featured_products, farmers=farmers)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        user_type = request.form.get('user_type')
        location = request.form.get('location')
        phone = request.form.get('phone')
        
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Email already registered!', 'danger')
            return redirect(url_for('register'))
        
        hashed_password = generate_password_hash(password)
        user = User(name=name, email=email, password=hashed_password, 
                   user_type=user_type, location=location, phone=phone)
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash(f'Welcome back, {user.name}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password!', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.user_type == 'farmer':
        products = Product.query.filter_by(farmer_id=current_user.id).all()
        orders = Order.query.join(OrderItem).join(Product).filter(Product.farmer_id == current_user.id).distinct().all()
        return render_template('dashboard.html', products=products, orders=orders)
    else:
        orders = Order.query.filter_by(user_id=current_user.id).all()
        cart_items = Cart.query.filter_by(user_id=current_user.id).all()
        return render_template('dashboard.html', orders=orders, cart_items=cart_items)

@app.route('/products')
def products():
    category = request.args.get('category')
    min_price = request.args.get('min_price')
    max_price = request.args.get('max_price')
    location = request.args.get('location')
    
    query = Product.query.filter_by(available=True)
    
    if category and category != '':
        query = query.filter_by(category=category)
    if min_price:
        query = query.filter(Product.price >= float(min_price))
    if max_price:
        query = query.filter(Product.price <= float(max_price))
    if location:
        farmers = User.query.filter_by(user_type='farmer', location=location).all()
        farmer_ids = [f.id for f in farmers]
        query = query.filter(Product.farmer_id.in_(farmer_ids))
    
    products = query.order_by(Product.created_at.desc()).all()
    categories = ['Vegetables', 'Fruits', 'Grains', 'Dairy', 'Meat', 'Organic', 'Other']
    
    return render_template('products.html', products=products, categories=categories)

@app.route('/product/<int:product_id>')
def product_detail(product_id):
    product = Product.query.get_or_404(product_id)
    reviews = Review.query.filter_by(product_id=product_id).all()
    return render_template('product_detail.html', product=product, reviews=reviews)

@app.route('/add_product', methods=['GET', 'POST'])
@login_required
def add_product():
    if current_user.user_type != 'farmer':
        flash('Only farmers can add products!', 'danger')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        category = request.form.get('category')
        price = float(request.form.get('price'))
        quantity = int(request.form.get('quantity'))
        unit = request.form.get('unit')
        description = request.form.get('description')
        
        image_file = request.files.get('image')
        filename = 'default_product.jpg'
        
        if image_file and image_file.filename:
            if allowed_file(image_file.filename):
                filename = secure_filename(f"{datetime.now().timestamp()}_{image_file.filename}")
                image_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        
        product = Product(name=name, category=category, price=price, 
                         quantity=quantity, unit=unit, description=description,
                         image=filename, farmer_id=current_user.id)
        
        db.session.add(product)
        db.session.commit()
        
        flash('Product added successfully!', 'success')
        return redirect(url_for('dashboard'))
    
    categories = ['Vegetables', 'Fruits', 'Grains', 'Dairy', 'Meat', 'Organic', 'Other']
    units = ['kg', 'dozen', 'piece', 'bundle', 'liter']
    return render_template('add_product.html', categories=categories, units=units)

@app.route('/edit_product/<int:product_id>', methods=['GET', 'POST'])
@login_required
def edit_product(product_id):
    product = Product.query.get_or_404(product_id)
    
    if current_user.user_type != 'farmer' or product.farmer_id != current_user.id:
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        product.name = request.form.get('name')
        product.category = request.form.get('category')
        product.price = float(request.form.get('price'))
        product.quantity = int(request.form.get('quantity'))
        product.unit = request.form.get('unit')
        product.description = request.form.get('description')
        product.available = 'available' in request.form
        
        image_file = request.files.get('image')
        if image_file and image_file.filename and allowed_file(image_file.filename):
            filename = secure_filename(f"{datetime.now().timestamp()}_{image_file.filename}")
            image_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            product.image = filename
        
        db.session.commit()
        flash('Product updated successfully!', 'success')
        return redirect(url_for('dashboard'))
    
    categories = ['Vegetables', 'Fruits', 'Grains', 'Dairy', 'Meat', 'Organic', 'Other']
    units = ['kg', 'dozen', 'piece', 'bundle', 'liter']
    return render_template('edit_product.html', product=product, categories=categories, units=units)

@app.route('/delete_product/<int:product_id>')
@login_required
def delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    
    if current_user.user_type != 'farmer' or product.farmer_id != current_user.id:
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('dashboard'))
    
    db.session.delete(product)
    db.session.commit()
    flash('Product deleted successfully!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/cart')
@login_required
def cart():
    cart_items = Cart.query.filter_by(user_id=current_user.id).all()
    total = sum(item.product.price * item.quantity for item in cart_items)
    return render_template('cart.html', cart_items=cart_items, total=total)

@app.route('/add_to_cart/<int:product_id>', methods=['POST'])
@login_required
def add_to_cart(product_id):
    if current_user.user_type != 'customer':
        flash('Only customers can add items to cart!', 'danger')
        return redirect(url_for('products'))
    
    quantity = int(request.form.get('quantity', 1))
    
    cart_item = Cart.query.filter_by(user_id=current_user.id, product_id=product_id).first()
    
    if cart_item:
        cart_item.quantity += quantity
    else:
        cart_item = Cart(user_id=current_user.id, product_id=product_id, quantity=quantity)
        db.session.add(cart_item)
    
    db.session.commit()
    flash('Product added to cart!', 'success')
    return redirect(url_for('cart'))

@app.route('/update_cart/<int:cart_id>', methods=['POST'])
@login_required
def update_cart(cart_id):
    cart_item = Cart.query.get_or_404(cart_id)
    
    if cart_item.user_id != current_user.id:
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('cart'))
    
    quantity = int(request.form.get('quantity'))
    
    if quantity > 0:
        cart_item.quantity = quantity
        db.session.commit()
    else:
        db.session.delete(cart_item)
        db.session.commit()
    
    return redirect(url_for('cart'))

@app.route('/remove_from_cart/<int:cart_id>')
@login_required
def remove_from_cart(cart_id):
    cart_item = Cart.query.get_or_404(cart_id)
    
    if cart_item.user_id != current_user.id:
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('cart'))
    
    db.session.delete(cart_item)
    db.session.commit()
    flash('Item removed from cart!', 'success')
    return redirect(url_for('cart'))

@app.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    if current_user.user_type != 'customer':
        flash('Only customers can checkout!', 'danger')
        return redirect(url_for('dashboard'))
    
    cart_items = Cart.query.filter_by(user_id=current_user.id).all()
    
    if not cart_items:
        flash('Your cart is empty!', 'warning')
        return redirect(url_for('products'))
    
    if request.method == 'POST':
        total = sum(item.product.price * item.quantity for item in cart_items)
        payment_method = request.form.get('payment_method')
        shipping_address = request.form.get('shipping_address')
        
        order = Order(user_id=current_user.id, total_amount=total,
                     payment_method=payment_method, shipping_address=shipping_address)
        db.session.add(order)
        db.session.flush()
        
        for cart_item in cart_items:
            order_item = OrderItem(order_id=order.id, product_id=cart_item.product_id,
                                  quantity=cart_item.quantity, price=cart_item.product.price)
            db.session.add(order_item)
            cart_item.product.quantity -= cart_item.quantity
        
        for cart_item in cart_items:
            db.session.delete(cart_item)
        
        db.session.commit()
        
        for item in order.items:
            notification = Notification(
                user_id=item.product.farmer_id,
                title='New Order Received!',
                message=f'New order for {item.quantity} {item.product.unit} of {item.product.name}'
            )
            db.session.add(notification)
        
        db.session.commit()
        
        flash('Order placed successfully!', 'success')
        return redirect(url_for('orders'))
    
    total = sum(item.product.price * item.quantity for item in cart_items)
    return render_template('checkout.html', cart_items=cart_items, total=total)

@app.route('/orders')
@login_required
def orders():
    if current_user.user_type == 'customer':
        orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()
    else:
        orders = Order.query.join(OrderItem).join(Product).filter(
            Product.farmer_id == current_user.id
        ).distinct().order_by(Order.created_at.desc()).all()
    
    return render_template('orders.html', orders=orders)

@app.route('/update_order/<int:order_id>', methods=['POST'])
@login_required
def update_order(order_id):
    order = Order.query.get_or_404(order_id)
    
    if current_user.user_type == 'farmer':
        has_product = any(item.product.farmer_id == current_user.id for item in order.items)
        if not has_product:
            flash('Unauthorized access!', 'danger')
            return redirect(url_for('orders'))
    
    status = request.form.get('status')
    order.status = status
    db.session.commit()
    
    notification = Notification(
        user_id=order.user_id,
        title='Order Status Updated',
        message=f'Your order #{order.id} status has been updated to {status}'
    )
    db.session.add(notification)
    db.session.commit()
    
    flash('Order status updated!', 'success')
    return redirect(url_for('orders'))

@app.route('/messages')
@login_required
def messages():
    sent_messages = Message.query.filter_by(sender_id=current_user.id).order_by(Message.created_at.desc()).all()
    received_messages = Message.query.filter_by(receiver_id=current_user.id).order_by(Message.created_at.desc()).all()
    
    unread_messages = Message.query.filter_by(receiver_id=current_user.id, read=False).all()
    for msg in unread_messages:
        msg.read = True
    db.session.commit()
    
    farmers = User.query.filter_by(user_type='farmer').all()
    customers = User.query.filter_by(user_type='customer').all()
    
    return render_template('messages.html', sent_messages=sent_messages, 
                         received_messages=received_messages, farmers=farmers, customers=customers)

@app.route('/send_message', methods=['POST'])
@login_required
def send_message():
    receiver_id = request.form.get('receiver_id')
    message_text = request.form.get('message')
    
    receiver = User.query.get(receiver_id)
    if not receiver:
        flash('User not found!', 'danger')
        return redirect(url_for('messages'))
    
    message = Message(sender_id=current_user.id, receiver_id=receiver_id, message=message_text)
    db.session.add(message)
    db.session.commit()
    
    flash('Message sent successfully!', 'success')
    return redirect(url_for('messages'))

@app.route('/add_review/<int:product_id>', methods=['POST'])
@login_required
def add_review(product_id):
    if current_user.user_type != 'customer':
        flash('Only customers can add reviews!', 'danger')
        return redirect(url_for('product_detail', product_id=product_id))
    
    rating = int(request.form.get('rating'))
    comment = request.form.get('comment')
    
    review = Review(user_id=current_user.id, product_id=product_id, 
                   rating=rating, comment=comment)
    db.session.add(review)
    db.session.commit()
    
    flash('Review added successfully!', 'success')
    return redirect(url_for('product_detail', product_id=product_id))

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        current_user.name = request.form.get('name')
        current_user.location = request.form.get('location')
        current_user.phone = request.form.get('phone')
        
        profile_pic = request.files.get('profile_pic')
        if profile_pic and profile_pic.filename and allowed_file(profile_pic.filename):
            filename = secure_filename(f"profile_{current_user.id}_{datetime.now().timestamp()}_{profile_pic.filename}")
            profile_pic.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            current_user.profile_pic = filename
        
        db.session.commit()
        flash('Profile updated successfully!', 'success')
    
    return render_template('profile.html')

@app.route('/notifications')
@login_required
def notifications():
    notifications = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).all()
    for notif in notifications:
        notif.read = True
    db.session.commit()
    return render_template('notifications.html', notifications=notifications)

# ==================== API ENDPOINTS ====================

@app.route('/api/farmers_nearby')
def farmers_nearby():
    location = request.args.get('location')
    if location:
        farmers = User.query.filter_by(user_type='farmer', location=location).all()
    else:
        farmers = User.query.filter_by(user_type='farmer').limit(10).all()
    
    farmers_list = [{
        'id': f.id,
        'name': f.name,
        'location': f.location,
        'phone': f.phone,
        'products_count': len(f.products)
    } for f in farmers]
    
    return jsonify(farmers_list)

@app.route('/api/product_price_comparison/<int:product_id>')
def product_price_comparison(product_id):
    product = Product.query.get(product_id)
    if not product:
        return jsonify({'error': 'Product not found'}), 404
    
    similar_products = Product.query.filter_by(
        name=product.name, 
        available=True
    ).all()
    
    comparison = [{
        'farmer_name': p.farmer.name,
        'price': p.price,
        'quantity': p.quantity,
        'location': p.farmer.location
    } for p in similar_products]
    
    return jsonify(comparison)

# ==================== NOTIFICATION API ENDPOINTS ====================

@app.route('/api/check_notifications')
@login_required
def check_notifications():
    """Check for new unread notifications"""
    notifications = Notification.query.filter_by(
        user_id=current_user.id, 
        read=False
    ).order_by(Notification.created_at.desc()).all()
    
    new_notifications = []
    for notif in notifications:
        new_notifications.append({
            'id': notif.id,
            'title': notif.title,
            'message': notif.message,
            'type': 'order' if 'Order' in notif.title else 'notification'
        })
    
    return jsonify({'new_notifications': new_notifications})

@app.route('/api/check_messages')
@login_required
def check_messages():
    """Check for new unread messages"""
    messages = Message.query.filter_by(
        receiver_id=current_user.id,
        read=False
    ).order_by(Message.created_at.desc()).all()
    
    new_messages = []
    for msg in messages:
        new_messages.append({
            'id': msg.id,
            'sender_name': msg.sender.name,
            'message': msg.message,
            'created_at': msg.created_at.strftime('%Y-%m-%d %H:%M')
        })
        msg.read = True
    
    db.session.commit()
    return jsonify({'new_messages': new_messages})

@app.route('/api/notification_count')
@login_required
def notification_count():
    """Get count of unread notifications"""
    count = Notification.query.filter_by(
        user_id=current_user.id,
        read=False
    ).count()
    return jsonify({'count': count})

@app.route('/api/message_count')
@login_required
def message_count():
    """Get count of unread messages"""
    count = Message.query.filter_by(
        receiver_id=current_user.id,
        read=False
    ).count()
    return jsonify({'count': count})

# ==================== DATABASE INITIALIZATION ====================

with app.app_context():
    db.create_all()
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    print("✓ Database initialized")
    print(f"✓ Upload folder created at: {app.config['UPLOAD_FOLDER']}")
    print("✓ Application ready to run!")

if __name__ == '__main__':
    app.run(debug=True)