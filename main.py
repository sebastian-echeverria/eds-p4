################################################################################################
# EDS - Spring 2012
# Project 4: Robust Group Photo Service
# Sebastian Echeverria
#
# TODO
#  - Manage case where new users add themselves to exiting retored transaction
#  - Manage timeout in separate thread (where? how?)
#  - Check for weird inputs (including invalid chars: :, # and |
#  - Check for weird or quick state changes
#  - Improve visuals
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
#  - Step 2: send info about status
#  - Step 2: receive recovery info
#  - Step 2: use recovery info
################################################################################################

################################################################################################
# Imports
################################################################################################
import os
import logging
import time
import socket
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

# Flag to see if we have initialized the app or not
initialized_app = False
restored_state = False

################################################################################################
# Class to store group info, including the status of the members
################################################################################################
groups = {}

class PhotoGroup:
    textReadyStatus     = 'Ready to upload'
    textSubmittedStatus = 'Image uploaded'
    textApprovedStatus  = 'Approved montage'
    textDoneStatus      = 'Done'

    def __init__(self, groupName, size, timeout):
        self.name = groupName
        self.size = int(size)
        self.timeout = timeout
        self.memberStatus = {}

    ################################################################################################
    # Functions to change the status of a user in a group
    ################################################################################################
    def setStatus(self, userName, status):
        self.memberStatus[userName] = status

    def setStatusReady(self, userName):
        self.setStatus(userName, self.textReadyStatus)

    def setStatusSubmitted(self, userName):
        self.setStatus(userName, self.textSubmittedStatus)
        
    def setStatusApproved(self, userName):
        self.setStatus(userName, self.textApprovedStatus)

    def setStatusDone(self, userName):
        self.setStatus(userName, self.textDoneStatus)

    ################################################################################################
    # Functions to change the status of ALL users in a group
    ################################################################################################
    def setAllReady(self):
        for userName in self.memberStatus.keys():
            self.setStatusReady(userName)

    def setAllSubmitted(self):
        for userName in self.memberStatus.keys():
            self.setStatusSubmitted(userName)

    def setAllDone(self):
        for userName in self.memberStatus.keys():
            self.setStatusDone(userName)

    ################################################################################################
    # Function to check current status for a specific
    ################################################################################################
    def isUserReady(self, userName):
        if userName in self.memberStatus.keys():        
            return self.memberStatus[userName] == self.textReadyStatus
        else:
            return False

    def isUserSubmitted(self, userName):
        if userName in self.memberStatus.keys():
            return self.memberStatus[userName] == self.textSubmittedStatus
        else:
            return False

    def isUserApproved(self, userName):
        if userName in self.memberStatus.keys():
            return self.memberStatus[userName] == self.textApprovedStatus
        else:
            return False

    def isUserDone(self, userName):
        if userName in self.memberStatus.keys():
            return self.memberStatus[userName] == self.textDoneStatus
        else:
            return False

    ################################################################################################
    # Function to check current status for the whole group
    ################################################################################################
    def checkAllReady(self):
        return self.checkAll(self.textReadyStatus)

    def checkAllSubmitted(self):
        return self.checkAll(self.textSubmittedStatus)

    def checkAllApproved(self):
        return self.checkAll(self.textApprovedStatus)

    def checkAllDone(self):
        return self.checkAll(self.textDoneStatus)

    def checkAll(self, expectedStatus):
        log = logging.getLogger('werkzeug')
        log.warning('Sizes ' + str(len(self.memberStatus.keys())) + ' ' + str(self.size))

        if(len(self.memberStatus.keys()) == self.size):
            # Check if everybody has submitted
            for key, status in self.memberStatus.items():
                if status != expectedStatus:
                    log.warning(key + " " + status)
                    return False

            # If everybody submitted, we are ok
            return True
        else:
            return False

    def anyUserReady(self):
        for status in self.memberStatus.values():
            if status == self.textReadyStatus:
                return True

        # If everybody submitted, we are ok
        return False

    def anyUserApproved(self):
        for status in self.memberStatus.values():
            if status == self.textApprovedStatus:
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
    # Logout
    session.pop('username', None)
    session.pop('groupname', None)
    session.pop('grouppath', None)

    # Restore state if necessary
    initApp();

    if request.method == 'POST':
        groupPath = app.config['UPLOAD_FOLDER'] + '/' + request.form['groupName']     

        # Create group if leader
        if request.form['loginType'] == 'Create':
            # Create folder for grup images
            if not os.path.exists(groupPath): 
                os.makedirs(groupPath)

            # Create object to store group information (request.form['timeout'])
            global groups
            groups[request.form['groupName']] = PhotoGroup(request.form['groupName'], request.form['groupSize'], 0)

            # Notify backend
            newGroup()

        # Before joining, check group exists and they aren't approving
        if (request.form['groupName'] not in groups.keys()):
            return redirect(url_for('errorPage', errorMsg="Group does not exist"))
        else:
            # Setup session, joining group
            session['username'] = request.form['userName']
            session['groupname'] = request.form['groupName']
            session['grouppath'] = groupPath

            # Depending on status from current Group, redirect to page that the user was before
            if groups[session['groupname']].isUserSubmitted(session['username'] ):
                return redirect(url_for('waitForMontage', groupName=session['groupname']))
            elif groups[session['groupname']].isUserApproved(session['username']):
                return redirect(url_for('waitForApproval', groupName=session['groupname']))
            elif groups[session['groupname']].isUserDone(session['username'] ):
                return redirect(url_for('commitMontage', groupName=session['groupname']))
            else:
                # Join group and go to upload page
                groups[session['groupname']].setStatusReady(session['username'])
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
            # Error about file extensions
            return redirect(url_for('errorPage', errorMsg="Invalid image to upload"))
    else:
        # We want to upload a new file
        return render_template('upload.html', name=groupName)

################################################################################################
# Waiting for other submissions   
################################################################################################
@app.route('/groups/<groupName>/waitForMontage')
def waitForMontage(groupName=None):
    if groups[session['groupname']].checkAllSubmitted() or groups[session['groupname']].anyUserApproved():
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

            # Save state to backend
            storeStatus()

            # Go to waiting page if required (or it will make us jump straight to commited state)
            return redirect(url_for('waitForApproval', groupName=session['groupname']))
        elif request.form['submitBtn'] == 'Reject':
            # Go to upload page, and send everybody else there too
            groups[session['groupname']].setAllReady()

            # Save state to backend
            storeStatus()

            return redirect(url_for('upload', groupName=session['groupname']))         
        else:   # Upload new Image
            # We have to mark everybody as "submitted", aborting transaction, and this user as "ready" to add an image
            groups[session['groupname']].setAllSubmitted()
            groups[session['groupname']].setStatusReady(session['username'])

            # Save state to backend
            storeStatus()

            return redirect(url_for('upload', groupName=session['groupname']))            

################################################################################################
# Waiting for the rest to approve, or jump to end if we're done
################################################################################################
@app.route('/groups/<groupName>/waitForApproval')
def waitForApproval(groupName=None):
    if groups[session['groupname']].checkAllApproved() or groups[session['groupname']].checkAllDone():
        groups[session['groupname']].setAllDone()
        
        # Notify backend
        endGroup()

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
# Show image function
################################################################################################
@app.route('/error/<errorMsg>')
def errorPage(errorMsg=None):
    return render_template('error.html', errorMsg=errorMsg)

################################################################################################
# Socket handling
################################################################################################
def newGroup():
    # Connect to backend
    port = 9995
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(('127.0.0.1', port))

    # Generate message
    msg = 'new:$'

    # Send status
    totalsent = 0
    while totalsent < len(msg):
        sent = s.send(msg[totalsent:])
        if sent == 0:
            raise RuntimeError("socket connection broken")
        totalsent = totalsent + sent

    s.close()

################################################################################################
# Socket handling
################################################################################################
def endGroup():
    # Connect to backend
    port = 9995
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(('127.0.0.1', port))

    # Generate message
    msg = 'remove:$'

    # Send status
    totalsent = 0
    while totalsent < len(msg):
        sent = s.send(msg[totalsent:])
        if sent == 0:
            raise RuntimeError("socket connection broken")
        totalsent = totalsent + sent

    s.close()

################################################################################################
# Socket handling
################################################################################################
def storeStatus():
    # Connect to backend
    port = 9995
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(('127.0.0.1', port))

    # Generate message
    status = groups[session['groupname']].memberStatus.items()
    msg = 'store:' + session['groupname'] + ':'
    for user, state in status:
        msg += user + '|' + state + '#' 
    msg += '$'

    # Send status
    totalsent = 0
    while totalsent < len(msg):
        sent = s.send(msg[totalsent:])
        if sent == 0:
            raise RuntimeError("socket connection broken")
        totalsent = totalsent + sent

    s.close()

################################################################################################
# Socket handling
################################################################################################
def restoreStatus():
    # Connect to backend
    port = 9995
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(('127.0.0.1', port))

    # Generate message
    msg = 'restore:$'

    # Send request
    totalsent = 0
    while totalsent < len(msg):
        sent = s.send(msg[totalsent:])
        if sent == 0:
            raise RuntimeError("socket connection broken")
        totalsent = totalsent + sent

    # Get answer, delimited by $
    chunkSize = 4096
    msg = ''
    while not '$' in msg:
        chunk = s.recv(chunkSize)
        if chunk == '':
            raise RuntimeError("socket connection broken")
        msg = msg + chunk

    # Parse and load data
    parseRestoreMsg(msg)

    s.close()

################################################################################################
# Parsing a restore message
################################################################################################
def parseRestoreMsg(msg):
    # Get group name
    parts = msg.split(':')
    if len(parts) == 0:
        # Nothing to restore
        return  
    else:
        global restored_state
        restored_state = True

    groupName = parts[0]

    # Get user section, count users, and create group data structure
    userData = parts[1].split('#')
    numUsers = len(userData)-1
    groups[groupName] = PhotoGroup(groupName, numUsers, 0)

    # Get info for each user
    for user in userData:
        splitData = user.split('|')
        if len(splitData) == 1:
            continue

        # Update group members with stored status
        userName = splitData[0]
        userStatus = splitData[1]
        groups[groupName].setStatus(userName, userStatus)

################################################################################################
# App intialization
################################################################################################
def initApp():
    global initialized_app
    if not initialized_app:
        initialized_app = True

################################################################################################
# Entry point to the app
################################################################################################
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')


