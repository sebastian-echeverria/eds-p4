################################################################################################
# EDS - Spring 2012
# Project 4: Robust Group Photo Service
# Sebastian Echeverria
#
# TODO
#  - Step 2: create and link with RVM server...
#  - Manage timeout in separate thread (where? how?)
#  - Check for weird inputs
#  - Check for weird or quick state changes
#
# DONE
#  - Obtain montage library
#  - Manage montaging
#  - Create montage accept/reject page and logic
#  - Create status page and final page
#  - Fix montage to use only user images, and 1 per user
#  - Auto- move to new montage
#  - Auto reload "waiting" pages
#  - Fix cached montage bug
#  - Make "Change pic" work
#  - Fix too-quick-steps bug
#  - Make "Reject" work
################################################################################################

################################################################################################
# Imports
################################################################################################
import os
import logging
import time
from flask import Flask, request, render_template, send_from_directory, redirect, url_for, session
from werkzeug import secure_filename

################################################################################################
# General app configuration
################################################################################################
app = Flask(__name__)

# Set upt folder to upload stuff to
UPLOAD_FOLDER = '/home/adminuser/eds-p4/static/uploads/'
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
    # Functions to change the status of a user (or users) in a group
    ################################################################################################
    def setStatusReady(self, userName):
        self.memberStatus[userName] = 'Ready to upload'

    def setStatusSubmitted(self, userName):
        self.memberStatus[userName] = 'Image uploaded'
        
    def setStatusApproved(self, userName):
        self.memberStatus[userName] = 'Approved montage'

    def setAllReady(self):
        for userName in self.memberStatus.keys():
            self.setStatusReady(userName)

    def setAllSubmitted(self):
        for userName in self.memberStatus.keys():
            self.setStatusSubmitted(userName)

    ################################################################################################
    # Function to check current status
    ################################################################################################
    def checkUserSubmitted(self, userName):
        return self.memberStatus[userName] == 'Image uploaded'

    def checkAllReady(self):
        return self.checkAll('Ready to upload')

    def checkAllSubmitted(self):
        return self.checkAll('Image uploaded')

    def checkAllApproved(self):
        return self.checkAll('Approved montage')

    def checkAll(self, expectedStatus):
        #log = logging.getLogger('werkzeug')
        #log.warning('Sizes ' + str(len(self.memberStatus.keys())) + ' ' + str(self.size))

        if(len(self.memberStatus.keys()) == self.size):
            # Check if everybody has submitted
            for status in self.memberStatus.values():
                if status != expectedStatus:
                    return False

            # If everybody submitted, we are ok
            return True
        else:
            return False

    def anyUserReady(self):
        for status in self.memberStatus.values():
            if status == 'Ready to upload':
                return True

        # If everybody submitted, we are ok
        return False
   
################################################################################################
# Utility functions to check if a filename has an allowed extension or to extract it
################################################################################################
ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg', 'gif'])

def getFilenameWithoutExt(filename):
    if '.' not in filename:
        return filename
    else:
        return filename.rsplit('.', 1)[0]

def getExt(filename):
    if '.' not in filename:
        return ''
    else:
        return filename.rsplit('.', 1)[1]

def allowed_file(filename):
    return '.' in filename and getExt(filename) in ALLOWED_EXTENSIONS

def cleanFiles(filePartialPath):
    for ext in ALLOWED_EXTENSIONS:
        fullpath = filePartialPath + '.' + ext
        if os.path.exists(fullpath):
            os.remove(fullpath)

def generateMontagePath(groupName):
    return '/static/uploads/' + groupName + '/'+ groupName + '.jpg' + '?' + str(time.time())

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
        groups[session['groupname']].setStatusReady(session['username'])

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
            # Remove any previous user images
            cleanFiles(os.path.join(session['grouppath'], session['username']))

            # Store new image for this user
            filename = session['username'] + '.' + getExt(file.filename)
            file.save(os.path.join(session['grouppath'], filename))

            # Update user status
            groups[session['groupname']].setStatusSubmitted(session['username'])

            # Check if we're ready for montage
            if groups[session['groupname']].checkAllSubmitted():
                return redirect(url_for('createMontage', groupName=session['groupname']))
            else:
                return redirect(url_for('waitForMontage', groupName=session['groupname']))
        else:
            # TODO: print some error about file extensions
            print Error
    else:
        # We want to upload a new file
        return render_template('upload.html', name=groupName)

################################################################################################
# Waiting for other submissions
################################################################################################
@app.route('/groups/<groupName>/waitForMontage')
def waitForMontage(groupName=None):
    if groups[session['groupname']].checkAllSubmitted():
        return redirect(url_for('approval', groupName=groupName))
    else:
        return render_template('waitForMontage.html', name=groupName, memberStatus=groups[session['groupname']].memberStatus)

################################################################################################
# Create the montage
################################################################################################
@app.route('/groups/<groupName>/montage')
def createMontage(groupName=None):

    montageCmd = 'montage '

    # Get all image filenames in a string
    users = groups[session['groupname']].memberStatus.keys()
    groupPath = app.config['UPLOAD_FOLDER'] + '/' + groupName + '/'
    listing = os.listdir(groupPath)
    memberImages = ''
    for infile in listing:
        # Check that is is a valid user image
        if getFilenameWithoutExt(infile) in users:
            # Concatenate to string of images
            memberImages += ' ' + groupPath + '/' + infile

    # Create montage
    montageFile = '  ' + groupPath + groupName + '.jpg'
    os.system(montageCmd + memberImages + montageFile)

    return redirect(url_for('approval', groupName=groupName))

################################################################################################
# Montage approval function (phase 1)
################################################################################################
@app.route('/groups/<groupName>/approval', methods=['GET', 'POST'])
def approval(groupName=None):
    if request.method == 'GET':
        if groups[session['groupname']].checkAllReady():
            # Someone aborted; we all go back to uploading...
            groups[session['groupname']].setStatusSubmitted(session['username'])
            return redirect(url_for('upload', groupName=session['groupname']))    
        elif groups[session['groupname']].anyUserReady():
            # Check if someone went back to change their pictures. If so, lets go wait for the new montage
            groups[session['groupname']].setStatusSubmitted(session['username'])
            return redirect(url_for('waitForMontage', groupName=session['groupname']))
        else:
            # Show montage for user to approve
            montagePath = generateMontagePath(groupName)
            return render_template('coordinate.html', name=groupName, montagePath=montagePath)
    elif request.method == 'POST':
        # Handle user approval
        if request.form['submitBtn'] == 'Approve':
            groups[session['groupname']].setStatusApproved(session['username']) 

            # Go to waiting page if required (or it will make us jump straight to commited state)
            return redirect(url_for('waitForApproval', groupName=session['groupname']))

        elif request.form['submitBtn'] == 'Reject':
            # Go to upload page, and send everybody else there too
            groups[session['groupname']].setAllReady()
            return redirect(url_for('upload', groupName=session['groupname']))         
        else:   # Upload new Image
            # We have to mark everybody as "submitted", aborting transaction, and this user as "ready" to add an image
            groups[session['groupname']].setAllSubmitted()
            groups[session['groupname']].setStatusReady(session['username'])
            return redirect(url_for('upload', groupName=session['groupname']))            

################################################################################################
# Waiting for the rest to approve, or jump to end if we're done
################################################################################################
@app.route('/groups/<groupName>/waitForApproval')
def waitForApproval(groupName=None):
    if groups[session['groupname']].checkAllApproved():
        return redirect(url_for('commitMontage', groupName=session['groupname']))
    elif groups[session['groupname']].checkAllReady():
        # Someone aborted; we all go back to uploading...
        groups[session['groupname']].setStatusSubmitted(session['username'])
        return redirect(url_for('upload', groupName=session['groupname']))    
    elif groups[session['groupname']].anyUserReady():
        # If we are in the "just submitted" status here, that means that the transaction was aborted while someone changes images
        # Let's go back to the "waiting for montage" page
        groups[session['groupname']].setStatusSubmitted(session['username'])
        return redirect(url_for('waitForMontage', groupName=session['groupname']))
    else:
        return render_template('waitForApproval.html', name=groupName, memberStatus=groups[session['groupname']].memberStatus)

################################################################################################
# Montage done!
################################################################################################
@app.route('/groups/<groupName>/done')
def commitMontage(groupName=None):
    # Show montage, final version
    montagePath = generateMontagePath(groupName)
    return render_template('done.html', name=groupName, montagePath=montagePath)

################################################################################################
# Show image function
################################################################################################
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(session['grouppath'], filename)

################################################################################################
# Socket handling
################################################################################################

#create an INET, STREAMing socket
#def storeIntent():
#    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#    s.connect((127.0.0.1, 9995))

################################################################################################
# Entry point to the app
################################################################################################
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')


