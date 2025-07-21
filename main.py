from flask import Flask, render_template, request, redirect, url_for
from google.cloud import firestore, storage
from google.cloud.firestore_v1.base_query import FieldFilter
# from builtins import print

app = Flask(__name__)
db = firestore.Client(project="s3979839-a1")

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
        # Valid credentials, redirect to forum
        return redirect(url_for('forum', id=id))
    return render_template('login.html', error=error)

@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        id = request.form.get('id')
        user_name = request.form.get('user_name')
        password = request.form.get('password')

        # Create FieldFilter
        field_filter_id = FieldFilter('id', '==', id)
        field_filter_user_name = FieldFilter('user_name', '==', user_name)

        # Query Firestore for a user with matching id or username
        users_ref = db.collection('user')
        
        # Check if ID exists
        id_exists = any(users_ref.where(filter=field_filter_id).stream())
        if id_exists:
            error = 'The ID already exists'
            return render_template('register.html', error=error)

        # Check if username exists
        username_exists = any(users_ref.where(filter=field_filter_user_name).stream())
        if username_exists:
            error = 'The username already exists'
            return render_template('register.html', error=error)

        # If no error, create the user
        # 1. Store user info in Firestore
        user_data = {
            'id': id,
            'user_name': user_name,
            'password': password
        }
        db.collection('user').add(user_data)

        # 2. Upload image to Google Cloud Storage
        image = request.files.get('image')
        if image:
            filename = filename.image
            storage_client = storage.Client()
            bucket = storage_client.bucket('user_avatar-a1')
            blob = bucket.blob('')
            blob.upload_from_file(image)
        
        # 3. Redirect to login
        return redirect(url_for('login'))
    return render_template('register.html', error=error)

if __name__ == '__main__':
    app.run(debug=True)