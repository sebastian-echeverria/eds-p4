################################################################################################
# EDS - Spring 2012
# Project 4: Robust Group Photo Service
# Sebastian Echeverria
################################################################################################

import socket
from photoGroup import PhotoGroup

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
    # Parsing a restore message. Returns a PhotoGroup
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
