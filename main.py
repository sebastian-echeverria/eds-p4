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
import logging
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
        self.size = int(size)
        self.timeout = timeout
        self.memberStatus = {}

    ################################################################################################
    # Functions to change the status of a user in a group
    ################################################################################################
    def setStatusJoined(self, userName):
        self.memberStatus[userName] = 'init'

    def setStatusSubmitted(self, userName):
        self.memberStatus[userName] = 'submit'
        
    def setStatusApproved(self, userName):
        self.memberStatus[userName] = 'approve'
        
    def setStatusAborted(self, userName):
        self.memberStatus[userName] = 'abort'

    ################################################################################################
    # Function to check if everybody has submitted an image
    ################################################################################################
    def checkAllSubmitted(self):
        #log = logging.getLogger('werkzeug')
        #log.warning('Sizes ' + str(len(self.memberStatus.keys())) + ' ' + str(self.size))

        if(len(self.memberStatus.keys()) == self.size):
            # Check if everybody has submitted
            for status in self.memberStatus.values():
                if status != 'submit':
                    return False

            # If everybody submitted, we are ok
            return True
        else:
            return False
    
################################################################################################
# Utility functions to check if a filename has an allowed extension
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
@app.route('/groups/<groupName>/upload', methods=['GET', 'POST'])
def upload(groupName=None):
    if request.method == 'POST':
        # Someone just uploaded a file
        file = request.files['newPhoto']
        if file and allowed_file(file.filename):
            # Store new image for this user
            filename = session['username'] + '.' + getExt(file.filename)
            file.save(os.path.join(session['grouppath'], filename))

            # Update user status
            groups[session['groupname']].setStatusSubmitted(session['username'])

            # Check if we're ready for montage
            if groups[session['groupname']].checkAllSubmitted():
                return redirect(url_for('createMontage', groupName=session['groupname']))
            else:
                return redirect(url_for('uploaded_file', filename=filename))
        else:
            # TODO: print some error about file extensions
            print Error
    else:
        # We want to upload a new file
        return render_template('upload.html', name=groupName)

################################################################################################
# Show image function
################################################################################################
@app.route('/groups/<groupName>/montage')
def createMontage(groupName=None):

    montageCmd = 'montage '

    # Get all image filenames in a string
    # TODO: check to do only once per user, instead of per file
    groupPath = app.config['UPLOAD_FOLDER'] + '/' + groupName + '/'
    listing = os.listdir(groupPath)
    memberImages = ''
    for infile in listing:
        memberImages += ' ' + groupPath + '/' + infile
    log = logging.getLogger('werkzeug')
    log.warning(memberImages)

    # Create montage
    montageFile = '  ' + groupPath + groupName + '.jpg'
    os.system(montageCmd + memberImages + montageFile)

    return send_from_directory(session['grouppath'], groupName + '.jpg')

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


