from flask import Flask, render_template, request, redirect, url_for, session
from google.cloud import firestore, storage
from google.cloud.firestore_v1.base_query import FieldFilter
from google.cloud.storage import bucket
from datetime import datetime
# from builtins import print

app = Flask(__name__)
app.secret_key = '9eNHcZ(D4c0/'  # Required for session management
db = firestore.Client(project="s3979839-a1")
storage_client = storage.Client()

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        # User submits login form, ID and Password
        id = request.form.get('id')
        password = request.form.get('password')
        
        # Create login_info dictionary contains user ID and Password from Firestore
        users_ref = db.collection('user')
        docs = users_ref.stream()
        login_info = {}
        
        for doc in docs:
            data = doc.to_dict()
            login_info[data['id']] = data['password']
        # print(login_info)

        # Check user credentials
        if id not in login_info or login_info[id] != password:
            error = 'ID or password is invalid'
            return render_template('login.html', error=error)
        
        # Valid credentials, save to session then redirect to forum
        session['id'] = id # Setting session variables
        session['login'] = True
        return redirect(url_for('forum', id=id))
    return render_template('login.html', error=error)

@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        user_id = request.form.get('id')
        user_name = request.form.get('user_name')
        password = request.form.get('password')

        # Query Firestore for a user with matching id or username
        users_ref = db.collection('user')
        
        # Check if ID exists
        id_exists = any(users_ref.where(filter=FieldFilter('id', '==', user_id)).stream())
        if id_exists:
            error = 'The ID already exists'
            return render_template('register.html', error=error)

        # Check if username exists
        username_exists = any(users_ref.where(filter=FieldFilter('user_name', '==', user_name)).stream())
        if username_exists:
            error = 'The username already exists'
            return render_template('register.html', error=error)

        # If no error, create the user
        # 1. Store user info in Firestore
        user_data = {
            'id': user_id,
            'user_name': user_name,
            'password': password
        }
        db.collection('user').add(user_data)

        # 2. Upload image to Google Cloud Storage
        user_image = request.files.get('user_image')
        if user_image:
            filename = f"{user_id}.png"
            bucket = storage_client.bucket('user_avatar-a1')
            blob = bucket.blob(filename)
            blob.upload_from_file(user_image)
            blob.make_public()
        
        # 3. Redirect to login
        return redirect(url_for('login'))
    return render_template('register.html', error=error)

@app.route('/forum', methods=['GET', 'POST'])
def forum():
    # Allow log in forum if
    # 1. checking login session, allow to /forum if user already login
    if 'login' not in session or not session['login']:
        return redirect(url_for('login'))
    
    # 2. also check user 'id', maintain identification
    user_id = session.get('id')
    if not user_id: return redirect(url_for('login'))

    # Get user information from Firestore, monitoring session
    users_ref = db.collection('user')
    user_docs = users_ref.where(filter=FieldFilter('id', '==', user_id)).stream()

    user_info = None
    for doc in user_docs:
        user_info = doc.to_dict()
        break

    if not user_info:
        # If user is not exist in db, clear session and redirect to login
        session.clear()
        return redirect(url_for('login'))
    

    # Checking if an user avatar filename exists on GCS
    user_avatar_filename = f"{user_id}.png"
    user_avatar_bucket = storage_client.bucket('user_avatar-a1')
    user_avatar_blob = user_avatar_bucket.blob(user_avatar_filename)
    default_avatar_blob = user_avatar_bucket.blob("default.png")
    
    # If exist then get URL for current login user avatar
    if user_avatar_blob.exists():
        avatar_url = user_avatar_blob.public_url
    else:
        avatar_url = default_avatar_blob.public_url

    if request.method == 'POST':
        subject = request.form.get('subject')
        message_text = request.form.get('message_text')
        message_image = request.files.get('message_image')

        if not subject: # If subject is empty, display list of 10 latest messages 
            messages = get_latest_messages(db, storage_client)
            # Rendering forum page with error for user
            return render_template('forum.html',
                                   user_name=user_info['user_name'],
                                   user_id=user_id,
                                   avatar_url=avatar_url,
                                   messages=messages,
                                   post_error="Subject cannot be empty.")
        
        # Store message metadata in dictionary 
        message_data = {
            'user_id': user_id,
            'user_name': user_info['user_name'],
            'subject': subject,
            'message_text': message_text,
            'timestamp': firestore.SERVER_TIMESTAMP # Update Firestore document Timestamp
        }
        
        # Store message post image in Google Cloud Storage
        image_url_for_post = None
        if message_image and message_image.filename != '':
            message_img = f"{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            posting_img_bucket = storage_client.bucket('posting_img-a1') 
            message_blob = posting_img_bucket.blob(message_img)
            message_blob.upload_from_file(message_image)
            message_blob.make_public()
            image_url_for_post = message_blob.public_url

        if image_url_for_post:
            message_data['image_url'] = image_url_for_post

        db.collection('messages').add(message_data) # Store into messages collection
        return redirect(url_for('forum'))                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   
    
    # Message display area
    messages = get_latest_messages(db, storage_client)
    return render_template('forum.html',
                           user_name=user_info['user_name'],
                           user_id=user_id,
                           avatar_url=avatar_url,
                           messages=messages,
                           post_error=None)

# Helper function to get latest messages from the top-level 'messages' collection
def get_latest_messages(db_client, storage_client_instance):
    messages_ref = db_client.collection('messages')
    query = messages_ref.order_by('timestamp', direction=firestore.Query.DESCENDING).limit(10)
    docs = query.stream()

    latest_messages = []
    user_avatar_bucket = storage_client_instance.bucket('user_avatar-a1') # Reference the user avatar bucket once
    
    # Extract all the info to display on message display area
    for doc in docs:
        message_data = doc.to_dict()
        message_data['display_time'] = message_data['timestamp'].strftime('%Y-%m-%d %H:%M:%S')

        # Checking if an poster avatar exists in GCS 
        poster_id = message_data.get('user_id')
        poster_avatar_filename = f"{poster_id}.png"
        poster_avatar_blob = user_avatar_bucket.blob(poster_avatar_filename)
        default_avatar_blob = user_avatar_bucket.blob("default.png")
        if poster_avatar_blob.exists():
            message_data['poster_avatar_url'] = poster_avatar_blob.public_url
        else:
            message_data['poster_avatar_url'] = default_avatar_blob.public_url

        latest_messages.append(message_data)
    return latest_messages

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/user_profile/<user_id>', methods=['GET', 'POST'])
def user_profile(user_id):
    if 'login' not in session or not session['login'] or session.get('id') != user_id:
        return redirect(url_for('login'))

    # Fetch user data from Firestore on user_id, check if the user data exists. If not, clear session
    user_data = None
    users_ref = db.collection('user')
    user_docs = users_ref.where(filter=FieldFilter('id', '==', user_id)).limit(1).get()
    user_doc_ref = None
    for doc in user_docs:
        user_data = doc.to_dict()
        user_doc_ref = doc.reference
        break
    
    if not user_data:
        session.clear()
        return "User not found", 404
    
    # Fetch user avatar from GCS on img_filename then create url for user avatar display
    img_filename = f"{user_id}.png"
    bucket = storage_client.bucket('user_avatar-a1')
    blob = bucket.blob(img_filename)
    default_blob = bucket.blob("default.png")
    if blob.exists():
        profile_avatar_url = blob.public_url
    else:
        profile_avatar_url = default_blob.public_url
    
    # Changing password session
    password_error = None
    if request.method == 'POST':
        form_type = request.form.get('form_type')
        if form_type == 'change_password':
            old_password = request.form.get('old_password')
            new_password = request.form.get('new_password')
            # Check if the user inputs correct old password, update if correct 
            if user_data['password'] == old_password:
                user_doc_ref.update({'password': new_password})
                session.clear()
                return redirect(url_for('login'))
            else:
                password_error = 'The old password is incorrect'
    
    # Get user's posts
    user_posts = []
    messages_ref = db.collection('messages')
    query = messages_ref.where(filter=FieldFilter('user_id', '==', user_id)).order_by('timestamp', direction=firestore.Query.DESCENDING).stream()
    for doc in query:
        post_data = doc.to_dict()
        post_data['id'] = doc.id
        post_data['display_time'] = post_data['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
        user_posts.append(post_data)

    return render_template('user_profile.html', 
                            user_data=user_data, 
                            profile_avatar_url=profile_avatar_url,
                            password_error=password_error,
                            user_posts=user_posts)

@app.route('/edit_post/<post_id>', methods=['GET', 'POST'])
def edit_post(post_id):
    if 'login' not in session or not session['login']:
        return redirect(url_for('login'))

    message_ref = db.collection('messages').document(post_id)
    message_doc = message_ref.get()

    if not message_doc.exists:
        return "Post not found", 404

    post_data = message_doc.to_dict()

    if session.get('id') != post_data['user_id']:
        return "Unauthorized", 403

    if request.method == 'POST':
        new_subject = request.form.get('subject')
        new_message_text = request.form.get('message_text')
        new_message_image = request.files.get('message_image')

        update_data = {
            'subject': new_subject,
            'message_text': new_message_text,
            'timestamp': firestore.SERVER_TIMESTAMP
        }

        # Handle image update
        if new_message_image and new_message_image.filename != '':
            # Delete old image if it exists
            if 'image_url' in post_data:
                old_image_url = post_data['image_url']
                # Extract blob name from URL
                old_blob_name = old_image_url.split('/')[-1].split('?')[0] # Remove URL parameters
                
                # Check if old_blob_name is a valid blob in the bucket before attempting to delete
                posting_img_bucket = storage_client.bucket('posting_img-a1')
                old_blob = posting_img_bucket.blob(old_blob_name)
                if old_blob.exists():
                    old_blob.delete()

            # Upload new image
            message_img = f"{post_data['user_id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            posting_img_bucket = storage_client.bucket('posting_img-a1')
            message_blob = posting_img_bucket.blob(message_img)
            message_blob.upload_from_file(new_message_image)
            message_blob.make_public()
            update_data['image_url'] = message_blob.public_url
        elif 'image_url' in post_data and not new_message_image: # If no new image uploaded and there was an old one
             # Keep the existing image_url
            pass
        elif 'image_url' in post_data and new_message_image and new_message_image.filename == '':
            # If the user explicitly clears the image by submitting an empty file input, remove the image
            if 'image_url' in post_data:
                old_image_url = post_data['image_url']
                old_blob_name = old_image_url.split('/')[-1].split('?')[0]
                posting_img_bucket = storage_client.bucket('posting_img-a1')
                old_blob = posting_img_bucket.blob(old_blob_name)
                if old_blob.exists():
                    old_blob.delete()
            if 'image_url' in update_data: # Ensure it's not set if user chose to remove
                del update_data['image_url']
            
            # Use .update() instead of .set() to merge the changes.
            message_ref.update({'image_url': firestore.DELETE_FIELD})


        message_ref.update(update_data)
        return redirect(url_for('forum'))

    return render_template('edit_post.html', post=post_data)

if __name__ == '__main__':
    app.run(debug=True)