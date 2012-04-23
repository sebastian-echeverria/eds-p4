//********************************************************************************
// EDS - Spring 2012
// Project 4: Robust Group Photo Service
// Sebastian Echeverria
//
// Based on libevent sample
//
// TODO:
//  - Store in RVM
//  - Read from RVM and send when requested
//  - Cleanup status after appproving (requires message?)
//********************************************************************************

#include <string.h>
#include <stdlib.h>
#include <errno.h>
#include <stdio.h>
#include <signal.h>

#include <sys/types.h>
#include <sys/stat.h>

#ifndef _WIN32
#include <netinet/in.h>
# ifdef _XOPEN_SOURCE_EXTENDED
#  include <arpa/inet.h>
# endif
#include <sys/socket.h>
#endif

#include <event2/bufferevent.h>
#include <event2/buffer.h>
#include <event2/listener.h>
#include <event2/util.h>
#include <event2/event.h>

#include <rvm/rds.h>
#include <rvm/rvm.h>

static const int PORT = 9995;

static const int MAX_GROUPINFO_SIZE = 1000;

static void accept_conn_cb(struct evconnlistener *, evutil_socket_t,
                           struct sockaddr *, int socklen, void *);
static void read_cb(struct bufferevent *bev, void *ctx);
static void read_event_cb(struct bufferevent *bev, short events, void *ctx);
static void signal_cb(evutil_socket_t, short, void *);

char* initRVM();
void newGroupSession();
int removeGroupSession();
int updateGroupSession(char* data, int dataLen);
void printStaticPointer();

// Persistent global variable with group info
char* g_groupState;

// Static area of RVM
char* g_staticArea;

//********************************************************************************
// Main
//********************************************************************************
int main(int argc, char **argv)
{
	struct event_base *base;
	struct evconnlistener *listener;
	struct event *signal_event;

	struct sockaddr_in sin;
#ifdef _WIN32
	WSADATA wsa_data;
	WSAStartup(0x0201, &wsa_data);
#endif

    // Setup libevent
    printf("Setting up\n");fflush(stdout);
	base = event_base_new();
	if (!base)
    {
		fprintf(stderr, "Could not initialize libevent!\n");
		return 1;
	}

    // Init RVM and group
    g_staticArea = initRVM();

    // Recover a group session if necessary
    printStaticPointer();
    memcpy(&g_groupState, g_staticArea, sizeof(g_groupState));

    // Init socket
	memset(&sin, 0, sizeof(sin));
	sin.sin_family = AF_INET;
	sin.sin_port = htons(PORT);

    // Setup listener for socket connections
    printf("Setting up listener\n");fflush(stdout);
	listener = evconnlistener_new_bind(base, accept_conn_cb, NULL,
	                                   LEV_OPT_REUSEABLE|LEV_OPT_CLOSE_ON_FREE, -1,
                                       (struct sockaddr*)&sin,
	                                   sizeof(sin));
	if (!listener)
    {
		fprintf(stderr, "Could not create a listener!\n");
		return 1;
	}

    // Setup signal event listener
	signal_event = evsignal_new(base, SIGINT, signal_cb, (void *)base);
	if (!signal_event || event_add(signal_event, NULL)<0)
    {
		fprintf(stderr, "Could not create/add a signal event!\n");
		return 1;
	}

    // Start libevent
	event_base_dispatch(base);

    // Free resources when done
	evconnlistener_free(listener);
	event_free(signal_event);
	event_base_free(base);

	printf("done\n");
	return 0;
}

//********************************************************************************
// Listener for socket events, called when we receive a connection
//********************************************************************************
static void accept_conn_cb(struct evconnlistener *listener, evutil_socket_t fd,
                           struct sockaddr *sa, int socklen, void *user_data)
{
    // We got a new connection! Set up a bufferevent for it
    struct event_base *base = evconnlistener_get_base(listener);
    struct bufferevent *bev = bufferevent_socket_new(base, fd, BEV_OPT_CLOSE_ON_FREE);
	if (!bev)
    {
		fprintf(stderr, "Error constructing bufferevent!");
		event_base_loopbreak(base);
		return;
	}

    printf("Connection accepted!\n");fflush(stdout);

    // Set callback for reading info, and set socket as read/write
    bufferevent_setcb(bev, read_cb, NULL, read_event_cb, NULL);
    bufferevent_enable(bev, EV_READ);
}

//********************************************************************************
// 
//********************************************************************************
void printStaticPointer()
{
    char* storedPointer;
    memcpy(&storedPointer, g_staticArea, sizeof(storedPointer));
    printf("Stored pointer: %p\n", storedPointer);
}

//********************************************************************************
// Event handler when there is data to be read
// General message format:
//   command:payload$
// New group:
//  -command = new
//  -payload = <empty>
// Store group info:
//  -command = new
//  -payload = <groupdata>
// Restore group info:
//  -command = restore
//  -payload = <empty>
// Remove group:
//  -command = remove
//  -payload = <empty>
//********************************************************************************
static void read_cb(struct bufferevent *bev, void *ctx)
{
    // Get input buffer
    struct evbuffer *input = bufferevent_get_input(bev);
    ev_uint32_t record_len = evbuffer_get_length(input);

    // Setup buffer to get data
    char* record = (char*) malloc(record_len);
    if (record == NULL)
        return;

    // Obtain data
    evbuffer_remove(input, record, record_len);

    // Store in structure
    //printf("Received: %s.\n", record);
    if(strncmp(record, "new", strlen("new")) == 0)
    {
        printf("Starting new session\n");
        newGroupSession();

        printStaticPointer();
    }
    else if(strncmp(record, "store", strlen("store")) == 0)
    {
        // Check start data marker
        char* start = strchr(record, ':') + 1;
        char* endMarker = strrchr(record, '$');
        int msgLength = endMarker - start + 1; // Include marker in saved data

        // Turn into string
        char* dataToStore = (char*) malloc(msgLength + 1);  // +1 for null terminator
        memset(dataToStore, 0, msgLength + 1);
        memcpy(dataToStore, start, msgLength);

        // Store data in RVM
        printf("Received: %s \n", dataToStore);
        if(!updateGroupSession(dataToStore, strlen(dataToStore)+1))
            printf("Couldn't update group session as there was no session loaded\n");
        else
            printf("Stored: %s \n", g_groupState);

        free(dataToStore);
    }
    else if(strncmp(record, "restore", strlen("restore")) == 0)
    {
        // Restore command received; send information back
        printf("Restore\n");
        struct evbuffer *output = bufferevent_get_output(bev);

        if(g_groupState != NULL)
        {
            printf("Sending %s.\n", g_groupState);
            evbuffer_add(output, g_groupState, strlen(g_groupState)+1);
        }
        else
        {
            evbuffer_add(output, "groupNotFound$", strlen("groupNotFound$")+1);
            printf("Couldn't restore group session as there was no session loaded\n");
        }
    }
    else if(strncmp(record, "remove", strlen("new")) == 0)
    {
        printf("Removing session\n");
        if(!removeGroupSession())
            printf("Couldn't remove group session as there was no session loaded\n");

        printStaticPointer();
    }
    else
    {
        printf("Invalid command received\n");
    }
}

//********************************************************************************
// Event handler for errors
//********************************************************************************
static void read_event_cb(struct bufferevent *bev, short events, void *ctx)
{
    if (events & BEV_EVENT_ERROR)
    {
        perror("Error from bufferevent");
    }
    if (events & (BEV_EVENT_EOF | BEV_EVENT_ERROR))
    {
        bufferevent_free(bev);
    }
}

//********************************************************************************
// System signal handler
//********************************************************************************
static void signal_cb(evutil_socket_t sig, short events, void *user_data)
{
	struct event_base *base = (struct event_base*) user_data;
	struct timeval delay = { 2, 0 };

	printf("Caught an interrupt signal; exiting cleanly in two seconds.\n");

	event_base_loopexit(base, &delay);
}

//********************************************************************************
// Initializes RVM access, returning a pointer to the static area
//********************************************************************************
char* initRVM()
{
    rvm_options_t* options;
    struct stat statbuf;
    rvm_offset_t data_len;
    char* static_area;
    int rc;

    // Initialize RVM
    options = rvm_malloc_options();
    options->log_dev = "../rvm/LOG";
    if (RVM_INIT(options) != RVM_SUCCESS)
    {
        fprintf(stderr, "RVM_INIT failed\n");
        exit(1);
    }

    // Set up the RDS allocator to manage the DATA file
    if (stat("../rvm/DATA", &statbuf) == -1)
        perror("stat(../rvm/DATA)");
    data_len.high = 0;
    data_len.low = statbuf.st_size;
    rds_load_heap("../rvm/DATA", data_len, &static_area, &rc);
    if (rc != SUCCESS)
    {
        fprintf(stderr, "rds_load_heap returned %d\n", rc);
        exit(1);
    }

    printf("RVM loaded correctly\n");
    return static_area;
}

//********************************************************************************
// Initializing permanent group structure
//********************************************************************************
void newGroupSession()
{    
    rvm_tid_t tid;
    rvm_init_tid(&tid);
    rvm_begin_transaction(&tid, restore);

    int rc;
    g_groupState = (char*) rds_malloc(MAX_GROUPINFO_SIZE, &tid, &rc);
    rvm_set_range(&tid, g_groupState, MAX_GROUPINFO_SIZE);

    // Store pointer in static area
    memcpy(g_staticArea, &g_groupState, sizeof(g_groupState));
    rvm_set_range(&tid, g_staticArea, sizeof(g_groupState));

    rvm_end_transaction(&tid, flush);
}

//********************************************************************************
// Initializing permanent group structure
//********************************************************************************
int removeGroupSession()
{    
    if(g_groupState == NULL)
        return 0;

    rvm_tid_t tid;
    rvm_init_tid(&tid);
    rvm_begin_transaction(&tid, restore);

    int rc;
    rds_free(g_groupState, &tid, &rc);
    rvm_set_range(&tid, g_groupState, MAX_GROUPINFO_SIZE);

    // Remove pointer
    memset(g_staticArea, 0, sizeof(char*));
    rvm_set_range(&tid, g_staticArea, sizeof(char*));
    g_groupState = NULL;

    rvm_end_transaction(&tid, flush);

    return 1;
}

//********************************************************************************
// Updating permanent group structure
//********************************************************************************
int updateGroupSession(char* data, int dataLen)
{
    // Check if we are actually in a sesison
    if(g_groupState == NULL)
        return 0;

    rvm_tid_t tid;
    rvm_init_tid(&tid);
    rvm_begin_transaction(&tid, restore);

    // Copy new data into permanent group info
    memcpy(g_groupState, data, dataLen);
    rvm_set_range(&tid, g_groupState, MAX_GROUPINFO_SIZE);

    rvm_end_transaction(&tid, flush);

    return 1;
}

