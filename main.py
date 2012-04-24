################################################################################################
# EDS - Spring 2012
# Project 4: Robust Group Photo Service
# Sebastian Echeverria
#
# TODO
#  - Improve how to get to a group directly through a link
#  - Remove hardcoded filesystem folder; obtain it relative somehow
#  - Manage case where new users add themselves to exiting restored transaction
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

# Set the secret key
app.secret_key = 'A0Zr98j/3yX R~XHH!aijdhwwi3kjha2384/,?RT'

################################################################################################
# File-related utility functions
################################################################################################

# Returns the name of a file without its extension
def getFilenameWithoutExt(filename):
    if '.' not in filename:
        return filename
    else:
        return filename.rsplit('.', 1)[0]

# Returns the extension of a filename
def getExt(filename):
    if '.' not in filename:
        return ''
    else:
        return filename.rsplit('.', 1)[1]

ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg', 'gif'])

# Checks if a file has an extension in the list of allowed extensions
def allowed_file(filename):
    return '.' in filename and getExt(filename) in ALLOWED_EXTENSIONS

# Removes all files in the given path/filename with the allowed extensions
def cleanFiles(filePathWithoutExt):
    for ext in ALLOWED_EXTENSIONS:
        fullpath = filePathWithoutExt + '.' + ext
        if os.path.exists(fullpath):
            os.remove(fullpath)

# URL path for montage picture
def generateMontagePath(groupName):
    return '/static/uploads/' + groupName + '/'+ groupName + '.jpg' + '?' + str(time.time())

################################################################################################
# Class to store group info, including the status of the members
################################################################################################

# Global variable to store the existing groups' information
groups = {}

# The class itself with group info
class PhotoGroup:
    # Full path where images will be stored for all groups
    UPLOAD_FOLDER = '/home/adminuser/eds-p4/static/uploads/'

    # Texts for each statuss
    textReadyStatus     = 'Ready to upload'
    textSubmittedStatus = 'Image uploaded'
    textApprovedStatus  = 'Approved montage'
    textDoneStatus      = 'Done'

    ################################################################################################
    # Constructor
    ################################################################################################
    def __init__(self, groupName, size, timeout):
        self.name = groupName
        self.size = int(size)
        self.timeout = timeout
        self.memberStatus = {}

    ################################################################################################
    # Function to get the full path where group images are stored
    ################################################################################################
    def getGroupFSPath(self):
        return self.UPLOAD_FOLDER + '/' + self.name
    
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

    ################################################################################################
    # Check if at least one user is in a specific state
    ################################################################################################
    def anyUserReady(self):
        for status in self.memberStatus.values():
            if status == self.textReadyStatus:
                return True

        # Nobody found in this state
        return False

    def anyUserApproved(self):
        for status in self.memberStatus.values():
            if status == self.textApprovedStatus:
                return True

        # Nobody found in this state
        return False

################################################################################################
# Class to handle network protocol to backend
################################################################################################
class BackendManager:
    # Port and host to connect to as a backend
    PORT = 9995
    HOST = '127.0.0.1'

    # Markers
    CMD_MARKER = ':'
    USR_MARKER = '#'
    DATA_MARKER = '|'
    END_MARKER = '$'
    
    ################################################################################################
    # Connect to backend
    ################################################################################################
    @staticmethod
    def connect():
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((BackendManager.HOST, BackendManager.PORT))
        return s

    ################################################################################################
    # Send request
    ################################################################################################
    @staticmethod
    def sendMessage(sock, msg):
        totalsent = 0
        while totalsent < len(msg):
            sent = sock.send(msg[totalsent:])
            if sent == 0:
                raise RuntimeError("socket connection broken")
            totalsent = totalsent + sent

    ################################################################################################
    # Get response, delimited by 
    ################################################################################################
    @staticmethod
    def getResponse(sock):
        # Get answer, delimited
        chunkSize = 4096
        msg = ''
        while not BackendManager.END_MARKER in msg:
            chunk = sock.recv(chunkSize)
            if chunk == '':
                raise RuntimeError("socket connection broken")
            msg = msg + chunk
        return msg

    ################################################################################################
    # Message to generate a new group
    ################################################################################################
    @staticmethod
    def createGroup():
        # Connect to backend
        sock = BackendManager.connect()

        # Generate and send message
        msg = 'new' + BackendManager.CMD_MARKER + BackendManager.END_MARKER
        BackendManager.sendMessage(sock, msg)

        sock.close()

    ################################################################################################
    # Message to destroy a group
    ################################################################################################
    @staticmethod
    def removeGroup():
        # Connect to backend
        sock = BackendManager.connect()

        # Generate message
        msg = 'remove' + BackendManager.CMD_MARKER + BackendManager.END_MARKER
        BackendManager.sendMessage(sock, msg)

        sock.close()

    ################################################################################################
    # Message to store group info
    ################################################################################################
    @staticmethod
    def storeGroupStatus(groupName, userData):
        # Connect to backend
        sock = BackendManager.connect()

        # Generate message
        msg = 'store' + BackendManager.CMD_MARKER + groupName + BackendManager.CMD_MARKER
        for user, state in userData:
            msg += user + BackendManager.DATA_MARKER + state + BackendManager.USR_MARKER
        msg += BackendManager.END_MARKER

        # Send msg
        BackendManager.sendMessage(sock, msg)

        sock.close()

    ################################################################################################
    # Socket handling
    ################################################################################################
    @staticmethod
    def getGroupStatus():        
        # Connect to backend
        sock = BackendManager.connect()

        # Generate message
        msg = 'restore' + BackendManager.CMD_MARKER + BackendManager.END_MARKER
        BackendManager.sendMessage(sock, msg)
        response = BackendManager.getResponse(sock)
        sock.close()

        # Parse and load data
        return BackendManager.parseRestoreMsg(msg)

    ################################################################################################
    # Parsing a restore message
    ################################################################################################
    @staticmethod
    def parseRestoreMsg(msg):
        # Get group name
        parts = msg.split(BackendManager.CMD_MARKER)
        if len(parts) < 2:
            # Nothing to restore
            return None

        # Get groupname
        groupName = parts[0]

        # Get user section, count users, and create group data structure
        userData = parts[1].split(BackendManager.USR_MARKER)
        numUsers = len(userData)-1
        group = PhotoGroup(groupName, numUsers, 0)

        # Get info for each user
        for user in userData:
            splitData = user.split(BackendManager.DATA_MARKER)
            if len(splitData) == 1:
                continue

            # Update group members with stored status
            userName = splitData[0]
            userStatus = splitData[1]
            group.setStatus(userName, userStatus)

        return group
  
################################################################################################
# Login functionality
################################################################################################
@app.route('/', methods=['GET', 'POST'])
def login():
    # Logout
    session.pop('username', None)

    if request.method == 'POST':
        # Create group if leader
        if request.form['loginType'] == 'Create':
            # Create object to store group information (request.form['timeout'])
            global groups
            groups[request.form['groupName']] = PhotoGroup(request.form['groupName'], request.form['groupSize'], 0)

            # Create folder for grup images
            groupPath = groups[request.form['groupName']].getGroupFSPath()
            if not os.path.exists(groupPath): 
                os.makedirs(groupPath)

            # Notify backend
            BackendManager.createGroup()

        # Before joining, check group exists and they aren't approving
        if (request.form['groupName'] not in groups.keys()):
            return redirect(url_for('errorPage', errorMsg="Group does not exist"))
        else:
            # Setup session, joining group
            userName = request.form['userName']
            session['username'] = userName
            groupName = request.form['groupName']
            group = groups[groupName]
            
            # Depending on status from current Group, redirect to page that the user was before
            if group.isUserSubmitted(userName):
                return redirect(url_for('waitForMontage', groupName=groupName))
            elif group.isUserApproved(userName):
                return redirect(url_for('waitForApproval', groupName=groupName))
            elif group.isUserDone(userName):
                return redirect(url_for('commitMontage', groupName=groupName))
            else:
                # Join group and go to upload page
                group.setStatusReady(userName)
                return redirect(url_for('upload', groupName=groupName))
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
            groupPath = groups[groupName].getGroupFSPath()
            cleanFiles(os.path.join(groupPath, session['username']))

            # Store new image for this user
            filename = session['username'] + '.' + getExt(file.filename)
            file.save(os.path.join(groupPath, filename))

            # Update user status
            groups[groupName].setStatusSubmitted(session['username'])

            # Check if we're ready for montage
            if groups[groupName].checkAllSubmitted():
                return redirect(url_for('createMontage', groupName=groupName))
            else:
                return redirect(url_for('waitForMontage', groupName=groupName))
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
    if groups[groupName].checkAllSubmitted() or groups[groupName].anyUserApproved():
        # If everybody just submitted a picture, or at least one already approved (is moving faster), go to approval page
        return redirect(url_for('approval', groupName=groupName))
    else:
        return render_template('waitForMontage.html', name=groupName, memberStatus=groups[groupName].memberStatus)

################################################################################################
# Create the montage
################################################################################################
@app.route('/groups/<groupName>/montage')
def createMontage(groupName=None):
    # System call to imagemagick program "montage"
    montageCmd = 'montage '

    # List all images in group file folder
    groupPath = groups[groupName].getGroupFSPath()
    listing = os.listdir(groupPath)

    # Put all valid image filenames in a parameters string
    users = groups[groupName].memberStatus.keys()
    memberImages = ''
    for imageFile in listing:
        # Check that is is a valid user image
        if getFilenameWithoutExt(imageFile) in users:
            # Concatenate to string of images
            memberImages += ' ' + groupPath + '/' + imageFile

    # Create montage
    montageFile = '  ' + groupPath + '/'  + groupName + '.jpg'
    os.system(montageCmd + memberImages + montageFile)

    return redirect(url_for('approval', groupName=groupName))

################################################################################################
# Montage approval function (phase 1)
################################################################################################
@app.route('/groups/<groupName>/approval', methods=['GET', 'POST'])
def approval(groupName=None):
    if request.method == 'GET':
        if groups[groupName].checkAllReady():
            # Someone aborted; we all go back to uploading...
            groups[groupName].setStatusSubmitted(session['username'])
            return redirect(url_for('upload', groupName=groupName))    
        elif groups[groupName].anyUserReady():
            # Check if someone went back to change their pictures. If so, lets go wait for the new montage
            groups[groupName].setStatusSubmitted(session['username'])
            return redirect(url_for('waitForMontage', groupName=groupName))
        else:
            # Show montage for user to approve
            montagePath = generateMontagePath(groupName)
            return render_template('coordinate.html', name=groupName, montagePath=montagePath)
    elif request.method == 'POST':
        # Handle user approval
        if request.form['submitBtn'] == 'Approve':
            groups[groupName].setStatusApproved(session['username']) 

            # Save state to backend
            BackendManager.storeGroupStatus(groupName, groups[groupName].memberStatus.items())

            # Go to waiting page if required (or it will make us jump straight to commited state)
            return redirect(url_for('waitForApproval', groupName=groupName))
        elif request.form['submitBtn'] == 'Reject':
            # Go to upload page, and send everybody else there too
            groups[groupName].setAllReady()

            # Save state to backend
            BackendManager.storeGroupStatus(groupName, groups[groupName].memberStatus.items())

            return redirect(url_for('upload', groupName=groupName))         
        else:   # Upload new Image
            # We have to mark everybody as "submitted", aborting transaction, and this user as "ready" to add an image
            groups[groupName].setAllSubmitted()
            groups[groupName].setStatusReady(session['username'])

            # Save state to backend
            BackendManager.storeGroupStatus(groupName, groups[groupName].memberStatus.items())

            return redirect(url_for('upload', groupName=groupName))            

################################################################################################
# Waiting for the rest to approve, or jump to end if we're done
################################################################################################
@app.route('/groups/<groupName>/waitForApproval')
def waitForApproval(groupName=None):
    if groups[groupName].checkAllApproved():
        # If all have just approved, mark everybody as done and notify backend to terminate group
        groups[groupName].setAllDone()
        BackendManager.removeGroup()
        
        # Go to final montage
        return redirect(url_for('commitMontage', groupName=groupName))
    elif groups[groupName].checkAllDone():
        # If somebody else already checked that all aproved and marked everybody as done, go see final montage
        return redirect(url_for('commitMontage', groupName=groupName))
    elif groups[groupName].checkAllReady():
        # Someone aborted; we all go back to uploading...
        groups[groupName].setStatusSubmitted(session['username'])
        return redirect(url_for('upload', groupName=groupName))    
    elif groups[groupName].anyUserReady():
        # If we are in the "just submitted" status here, that means that the transaction was aborted while someone changes images
        # Let's go back to the "waiting for montage" page
        groups[groupName].setStatusSubmitted(session['username'])
        return redirect(url_for('waitForMontage', groupName=groupName))
    else:
        return render_template('waitForApproval.html', name=groupName, memberStatus=groups[groupName].memberStatus)

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
    groupPath = groups[groupName].getGroupFSPath()
    return send_from_directory(groupPath, filename)

################################################################################################
# Show image function
################################################################################################
@app.route('/error/<errorMsg>')
def errorPage(errorMsg=None):
    return render_template('error.html', errorMsg=errorMsg)

################################################################################################
# Restores a group
################################################################################################
def restoreStatus():
    group = BackendManager.getGroupStatus()
    if group is not None:
        groups[group.name] = group

################################################################################################
# Entry point to the app
################################################################################################
if __name__ == '__main__':
    # Restore state if necessary
    restoreStatus()
    app.run(debug=True, host='0.0.0.0')

