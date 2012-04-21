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
UPLOAD_FOLDER = '/home/adminuser/eds-p4/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Set the secret key
app.secret_key = 'A0Zr98j/3yX R~XHH!aijdhwwi3kjha2384/,?RT'

################################################################################################
# Class to store group info, including the status of the members
################################################################################################
groups = {}

class PhotoGroup:
    def __init__(self, groupName, size, timeout):
        self.name = groupName
        self.size = size
        self.timeout = timeout
        self.memberStatus = {}

    def setStatusJoined(self, userName):
        self.memberStatus[userName] = 'init'

    def setStatusSubmitted(self, userName):
        self.memberStatus[userName] = 'submit'
        
    def setStatusApproved(self, userName):
        self.memberStatus[userName] = 'approve'
        
    def setStatusAborted(self, userName):
        self.memberStatus[userName] = 'abort'        
    

################################################################################################
# Utility function to check if a filename has an allowed extension
################################################################################################
ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg', 'gif'])

def getExt(filename):
    if '.' not in filename:
        return ''
    else:
        return filename.rsplit('.', 1)[1]

def allowed_file(filename):
    return '.' in filename and getExt(filename) in ALLOWED_EXTENSIONS

################################################################################################
# Login functionality
################################################################################################
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Setup session, joining group
        session['username'] = request.form['userName']
        session['groupname'] = request.form['groupName']
        session['grouppath'] = app.config['UPLOAD_FOLDER'] + '/' + session['groupname']

        # Create group if leader
        if request.form['loginType'] == 'Create':
            # Create folder for grup images           
            if not os.path.exists(session['grouppath']): 
                os.makedirs(session['grouppath'])

            # Create object to store group information 
            global groups
            groups[session['groupname']] = PhotoGroup(request.form['groupName'], request.form['groupSize'], request.form['timeout'])
        
        # Join group
        groups[session['groupname']].setStatusJoined(session['username'])

        # Go to upload page 
        return redirect(url_for('upload', groupName=session['groupname']))
    else:
        return render_template('login.html')

################################################################################################
# Upload image functionality
################################################################################################
@app.route('/groups/<groupName>', methods=['GET', 'POST'])
def upload(groupName=None):
    if request.method == 'POST':
        file = request.files['newPhoto']
        if file and allowed_file(file.filename):
            # Store new image for this user
            filename = session['username'] + '.' + getExt(file.filename)
            file.save(os.path.join(session['grouppath'], filename))

            # Update user status
            groups[session['groupname']].setStatusSubmitted(session['username'])
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


