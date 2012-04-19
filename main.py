################################################################################################
# EDS - Spring 2012
# Project 4: Robust Group Photo Service
# Sebastian Echeverria
#
# TODO
#  - Obtain montage library
#  - Manage timeout and montaging in separate thread (where? how?)
#  - Create montage accept/reject page and logic
#  - Create status page and final page
#  - Step 2: create and link with RVM server...
#
################################################################################################

################################################################################################
# Imports
################################################################################################
import os
from flask import Flask, request, render_template, send_from_directory, redirect, url_for, session
from werkzeug import secure_filename

################################################################################################
# General app configuration
################################################################################################
app = Flask(__name__)

# Set upt folder to upload stuff to
UPLOAD_FOLDER = '/home/adminuser/testproject/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Set the secret key
app.secret_key = 'A0Zr98j/3yX R~XHH!aijdhwwi3kjha2384/,?RT'

################################################################################################
# Utility function to check if a filename has an allowed extension
################################################################################################
ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg', 'gif'])

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS

################################################################################################
# Login functionality
################################################################################################
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Setup session, joining group
        session['username'] = request.form['userName']
        session['groupname'] = request.form['groupName']
        session['grouppath'] = UPLOAD_FOLDER + '/' + session['groupname']

        # Create group
        if request.form['loginType'] == 'Create':            
            if not os.path.exists(session['groupPath']): 
                os.makedirs(session['groupPath'])
            # TODO: Do something to create a group with the given size and timeout

        # Go to upload page 
        return redirect(url_for('group', groupName=session['groupname']))
    else:
        return render_template('login.html')

################################################################################################
# Upload image functionality
################################################################################################
@app.route('/groups/<groupName>', methods=['GET', 'POST'])
def group(groupName=None):
    if request.method == 'POST':
        file = request.files['newPhoto']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(session['grouppath'], filename))
            #return render_template('group.html', name=groupName, filename=filename)
            return redirect(url_for('uploaded_file', filename=filename))
    else:
        return render_template('group.html', name=groupName)

################################################################################################
# Show image function
################################################################################################
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(session['grouppath'], filename)

################################################################################################
# Entry point to the app
################################################################################################
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')


