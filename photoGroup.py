################################################################################################
# EDS - Spring 2012
# Project 4: Robust Group Photo Service
# Sebastian Echeverria
################################################################################################

import os
import time

################################################################################################
# Class to store group info, including the status of the members
################################################################################################

# The class itself with group info
class PhotoGroup:
    # Full path where images will be stored for all groups
    UPLOAD_FOLDER = '/static/uploads/'

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

    def getUsers(self):
        return self.memberStatus.keys()

    def getUsersStatus(self):
        return self.memberStatus.items()

    ################################################################################################
    # Function to get the full path where group images are stored, and relative for montage
    ################################################################################################
    def getGroupFSPath(self):
        return os.getcwd() + self.UPLOAD_FOLDER + '/' + self.name

    def generateMontagePath(self):
        return self.UPLOAD_FOLDER + self.name + '/'+ self.name + '.jpg' + '?' + str(time.time())
    
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

    def checkAllApprovedOrDone(self):
        if(len(self.memberStatus.keys()) == self.size):
            # Check if everybody has submitted
            for key, status in self.memberStatus.items():
                if (status != self.textApprovedStatus) and (status != self.textDoneStatus):
                    return False

            # If everybody submitted, we are ok
            return True
        else:
            return False

    def checkAll(self, expectedStatus):
        #log('Sizes ' + str(len(self.memberStatus.keys())) + ' ' + str(self.size))

        if(len(self.memberStatus.keys()) == self.size):
            # Check if everybody has submitted
            for key, status in self.memberStatus.items():
                if status != expectedStatus:
                    #log(key + " " + status)
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

