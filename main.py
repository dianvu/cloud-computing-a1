from flask import Flask, render_template, request, redirect, url_for
from google.cloud import firestore
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
        user_id = request.form.get('id')
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
        if user_id not in login_info or login_info[user_id] != password:
            error = 'ID or password is invalid'
            return render_template('login.html', error=error)
        # Valid credentials, redirect to forum
        return redirect(url_for('forum', user_name=user_id))
    return render_template('login.html', error=error)

@app.route('/forum')
def forum():
    user_name = request.args.get('user_name', 'User')
    return render_template('forum.html', user_name=user_name)

if __name__ == '__main__':
    app.run(debug=True)