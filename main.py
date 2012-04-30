################################################################################################
# EDS - Spring 2012
# Project 4: Robust Group Photo Service
# Sebastian Echeverria
#
# TODO
#  - Improve visuals (CSS)
#
# NOT DO
#  - Use AJAX > too complicated
#  - Manage timeout in separate thread (where? how?) > groupsize instead of first timeout
#  - Improve how to get to a group directly through a link > good enough, go to main an input group name (plus username)
#  - Check for weird or quick state changes > too complicated
#  - Check for weird inputs (including invalid chars: :, # and | > not worth it
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
#  - Remove hardcoded filesystem folder; obtain it relative somehow
#  - Fix Reject (post change pic) bug fRwith 3 devices (one Android)
#  - Check for missing inputs
#  - Fix restore bug
#  - Manage case where new users add themselves to exiting restored transaction
#  - Add timeout for votes
#  - Improve montage
################################################################################################

################################################################################################
# Imports
################################################################################################
import os
import logging
import time
from flask import Flask, request, render_template, send_from_directory, redirect, url_for, session

# Internal imports
from photoGroup import PhotoGroup
from backendMan import BackendManager

################################################################################################
# General app configuration
################################################################################################
app = Flask(__name__)

# Set the secret key
app.secret_key = 'A0Zr98j/3yX R~XHH!aijdhwwi3kjha2384/,?RT'

################################################################################################
# Internal logger
################################################################################################
def log(msg):
    log = logging.getLogger('werkzeug')
    log.warning(msg)

################################################################################################
# Generic file utils
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

# Removes all files in the given folder
def cleanAllFiles(folderPath):
    listing = os.listdir(folderPath)
    for imageFile in listing:
        os.remove(folderPath + "/" + imageFile)

################################################################################################
# File function for allowed images and image folder handling
################################################################################################

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

################################################################################################
# Global variable to store the existing groups' information
################################################################################################
g_groups = {}

def setGroup(group):
    global g_groups
    g_groups.clear()  # As the backend is only supporting 1 group at a time, we'll clear all the rest to be consistent
    g_groups[group.name] = group    

def getGroup(groupName):
    global g_groups
    if groupName in g_groups.keys():
        return g_groups[groupName]
    else:
        return None
  
################################################################################################
# Login functionality
################################################################################################
@app.route('/', methods=['GET', 'POST'])
def login():
    # Logout
    session.pop('username', None)

    if request.method == 'POST':
        # Validate input
        if (request.form['userName'] == ''):
            return redirect(url_for('errorPage', errorMsg="userNotSelected"))
        if (request.form['groupName'] == ''):
            return redirect(url_for('errorPage', errorMsg="groupNotSelected"))

        # Create group if leader
        if request.form['loginType'] == 'Create':
            if (request.form['groupSize'] == ''):
                return redirect(url_for('errorPage', errorMsg="sizeNotSelected"))

            # Trim and get group size
            try:
                groupSize = str(int(request.form['groupSize']))
            except:
                return redirect(url_for('errorPage', errorMsg="groupSizeNotValid"))

            # Create object to store group information
            group = PhotoGroup(request.form['groupName'], groupSize, 0)
            setGroup(group)

            # Create folder for grup images
            groupPath = group.getGroupFSPath()
            if not os.path.exists(groupPath): 
                os.makedirs(groupPath)
            cleanAllFiles(groupPath)

            # Notify backend
            BackendManager.createGroup()

        # Before joining, check group exists
        groupName = request.form['groupName']
        group = getGroup(groupName)
        if (group is None):
            return redirect(url_for('errorPage', errorMsg="nonExistentGroup"))

        # Now check if there are spaces available
        if(not group.isInGroup(request.form['userName'])) and (not group.isSpaceAvailable()):
            return redirect(url_for('errorPage', errorMsg="maxUsersReached"))

        # Setup session, joining group
        userName = request.form['userName']
        session['username'] = userName            
        
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
            # Get the username from the session, or if we came from out of it, from the form
            if 'username' in session.keys():
                userName = session['username']
            else:
                userName = request.form['username']

            # Group check
            group = getGroup(groupName)
            if (group is None):
                return redirect(url_for('errorPage', errorMsg="nonExistentGroup"))

            # Remove any previous user images
            groupPath = group.getGroupFSPath()
            cleanFiles(os.path.join(groupPath, userName))

            # Store new image for this user
            filename = userName + '.' + getExt(file.filename)
            file.save(os.path.join(groupPath, filename))

            # Update user status
            group.setStatusSubmitted(userName)

            # Check if we're ready for montage
            if group.checkAllSubmitted():
                group.startTimer()
                return redirect(url_for('createMontage', groupName=groupName))
            else:
                return redirect(url_for('waitForMontage', groupName=groupName))
        else:
            # Error about file extensions
            return redirect(url_for('errorPage', errorMsg="invalidFile"))
    else:
        # We want to upload a new file
        groupURL = request.base_url.replace('http', 'picshare')
        return render_template('upload.html', name=groupName, groupURL=groupURL, username=session['username'])

################################################################################################
# Waiting for other submissions   
################################################################################################
@app.route('/groups/<groupName>/waitForMontage')
def waitForMontage(groupName=None):
    # Group check
    group = getGroup(groupName)
    if (group is None):
        return redirect(url_for('errorPage', errorMsg="nonExistentGroup"))

    # User check
    if(not session['username'] or not group.isInGroup(session['username'])):
        return redirect(url_for('errorPage', errorMsg="userIsNotInGroup"))

    if group.checkAllSubmitted() or group.anyUserApproved():
        # If everybody just submitted a picture, or at least one already approved (is moving faster), go to approval page
        return redirect(url_for('approval', groupName=groupName))
    else:
        return render_template('waitForMontage.html', name=groupName, memberStatus=group.getUsersStatus(), size=group.size)

################################################################################################
# Create the montage
################################################################################################
@app.route('/groups/<groupName>/montage')
def createMontage(groupName=None):
    # Group check
    group = getGroup(groupName)
    if (group is None):
        return redirect(url_for('errorPage', errorMsg="nonExistentGroup"))

    # System call to imagemagick program "montage"
    montageCmd = 'montage '

    # List all images in group file folder
    groupPath = group.getGroupFSPath()
    listing = os.listdir(groupPath)

    # Put all valid image filenames in a parameters string
    users = group.getUsers()
    memberImages = ''
    for imageFile in listing:
        # Check that is is a valid user image
        if getFilenameWithoutExt(imageFile) in users:
            # Concatenate to string of images
            memberImages += ' ' + groupPath + '/' + imageFile

    # Create montage
    montageFile = '  -background SkyBlue  ' + groupPath + '/'  + groupName + '.jpg'
    log(montageCmd + memberImages + montageFile)
    os.system(montageCmd + memberImages + montageFile)
    time.sleep(1)

    return redirect(url_for('approval', groupName=groupName))

################################################################################################
# Montage approval function (phase 1)
################################################################################################
@app.route('/groups/<groupName>/approval', methods=['GET', 'POST'])
def approval(groupName=None):
    # Group check
    group = getGroup(groupName)
    if (group is None):
        return redirect(url_for('errorPage', errorMsg="nonExistentGroup"))

    # User check
    if(not session['username'] or not group.isInGroup(session['username'])):
        return redirect(url_for('errorPage', errorMsg="userIsNotInGroup"))

    if group.isTimeUp():
        group.stopTimer()
        group.setAllReady()
        BackendManager.storeGroupStatus(groupName, group.getUsersStatus()) 
        return redirect(url_for('upload', groupName=groupName))            

    if request.method == 'GET':
        if group.checkAllReady():
            # Someone aborted; we all go back to uploading...
            return redirect(url_for('upload', groupName=groupName))    
        elif group.anyUserReady():
            # Check if someone went back to change their pictures. If so, lets go wait for the new montage
            group.setStatusSubmitted(session['username'])
            return redirect(url_for('waitForMontage', groupName=groupName))
        else:
            # Show montage for user to approve
            montagePath = group.generateMontagePath()
            return render_template('coordinate.html', name=groupName, montagePath=montagePath)
    elif request.method == 'POST':
        # Handle user approval
        if request.form['submitBtn'] == 'Approve':
            group.setStatusApproved(session['username']) 

            # Save state to backend
            BackendManager.storeGroupStatus(groupName, group.getUsersStatus())

            # Go to waiting page if required (or it will make us jump straight to commited state)
            return redirect(url_for('waitForApproval', groupName=groupName))
        elif request.form['submitBtn'] == 'Reject':
            # Move everybody back to the "ready to upload" phase
            group.setAllReady()

            # Save state to backend
            BackendManager.storeGroupStatus(groupName, group.getUsersStatus()) 
            return redirect(url_for('upload', groupName=groupName))         
        else:   # Upload new Image
            # We send everybody to "waiting for other pictures" except for the current one, which goes to "ready to upload"
            group.setAllSubmitted()
            group.setStatusReady(session['username'])

            # Save state to backend
            BackendManager.storeGroupStatus(groupName, group.getUsersStatus())

            return redirect(url_for('upload', groupName=groupName))            

################################################################################################
# Waiting for the rest to approve, or jump to end if we're done
################################################################################################
@app.route('/groups/<groupName>/waitForApproval')
def waitForApproval(groupName=None):
    # Group check
    group = getGroup(groupName)
    if (group is None):
        return redirect(url_for('errorPage', errorMsg="nonExistentGroup"))

    # User check
    if(not session['username'] or not group.isInGroup(session['username'])):
        return redirect(url_for('errorPage', errorMsg="userIsNotInGroup"))

    if group.isTimeUp():
        group.stopTimer()
        group.setAllReady()
        BackendManager.storeGroupStatus(groupName, group.getUsersStatus()) 
        return redirect(url_for('upload', groupName=groupName))            

    if group.checkAllApprovedOrDone():
        # All have approved! Set this user as done (all have approved and he will know about it now)
        group.setStatusDone(session['username'])

        if group.checkAllDone():
            # If we are the last one asking for the montage status, remove session
            BackendManager.removeGroup()

        # Show the montage to the user
        return redirect(url_for('commitMontage', groupName=groupName))
    elif group.checkAllReady():
        # Someone aborted; we all go back to uploading...
        return redirect(url_for('upload', groupName=groupName))    
    elif group.anyUserReady():
        # Someone aborted to change their image; let's go back to the "waiting for montage" page
        group.setStatusSubmitted(session['username'])
        return redirect(url_for('waitForMontage', groupName=groupName))
    else:
        # Nothing new that is useful; still waiting for approvals or one abort
        return render_template('waitForApproval.html', name=groupName, memberStatus=group.getUsersStatus())

################################################################################################
# Montage done!
################################################################################################
@app.route('/groups/<groupName>/done')
def commitMontage(groupName=None):
    # Group check
    group = getGroup(groupName)
    if (group is None):
        return redirect(url_for('errorPage', errorMsg="nonExistentGroup"))

    # User check
    if(not session['username'] or not group.isInGroup(session['username'])):
        return redirect(url_for('errorPage', errorMsg="userIsNotInGroup"))

    # Show montage, final version
    montagePath = group.generateMontagePath()
    return render_template('done.html', name=groupName, montagePath=montagePath)

################################################################################################
# Show image function
################################################################################################
@app.route('/uploads/<groupName>/<filename>')
def uploaded_file(filename, groupName=None):
    # Group check
    group = getGroup(groupName)
    if (group is None):
        return redirect(url_for('errorPage', errorMsg="nonExistentGroup"))

    groupPath = group.getGroupFSPath()
    return send_from_directory(groupPath, filename)

################################################################################################
# Show image function
################################################################################################
@app.route('/error/<errorMsg>')
def errorPage(errorMsg=None):
    errorMsgString = 'Unknown error'

    if(errorMsg == 'nonExistentGroup'):
        errorMsgString = 'Group does not exist'
    elif(errorMsg == 'invalidFile'):
        errorMsgString = 'Invalid image to upload'
    elif(errorMsg == 'groupNotSelected'):
        errorMsgString = 'Please indicate a group name'
    elif(errorMsg == 'userNotSelected'):
        errorMsgString = 'Please indicate a user name'
    elif(errorMsg == 'sizeNotSelected'):
        errorMsgString = 'Please indicate a group size'
    elif(errorMsg == 'groupSizeNotValid'):
        errorMsgString = 'Please indicate a valid group size'
    elif(errorMsg == 'maxUsersReached'):
        errorMsgString = 'Cant join group, number of registered users has reached the maximum for the group.'
    elif(errorMsg == 'userIsNotInGroup'):
        errorMsgString = 'User is not (or no longer) in this group.'
    
    return render_template('error.html', errorMsgString=errorMsgString)

################################################################################################
# Restores a group
################################################################################################
def restoreStatus():
    group = BackendManager.getGroupStatus()
    if group is not None:
        setGroup(group)

################################################################################################
# Entry point to the app
################################################################################################
if __name__ == '__main__':
    # Restore state if necessary
    restoreStatus()
    app.run(debug=True, host='0.0.0.0')

