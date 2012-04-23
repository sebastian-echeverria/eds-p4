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

struct Group
{
    char* name;
    char* userInfoString;
};


static void accept_conn_cb(struct evconnlistener *, evutil_socket_t,
                           struct sockaddr *, int socklen, void *);
static void read_cb(struct bufferevent *bev, void *ctx);
static void read_event_cb(struct bufferevent *bev, short events, void *ctx);
static void signal_cb(evutil_socket_t, short, void *);
struct Group* parseMsg(char* msg);

struct Group* theGroup;

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
// Event handler when there is data to be read
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
    printf("Received: %s.\n", record);
    if(strncmp(record, "restore", strlen("restore")) == 0)
    {
        // Restore command received; send information back
        char fakeGroup[] = "fake:u1|Image uploaded#u2|Approved montage#$";
        struct evbuffer *output = bufferevent_get_output(bev);

        /* Copy all the data from the input buffer to the output buffer. */
        evbuffer_add(output, fakeGroup, sizeof(fakeGroup));
    }
    else if(strncmp(record, "store", strlen("store")) == 0)
    {
        theGroup = parseMsg(record+strlen("store:"));

        // Print what we received
        printf("Group name: %s (length=%d)\n", theGroup->name, strlen(theGroup->name));
        printf("Group info: %s (length=%d)\n", theGroup->userInfoString, strlen(theGroup->userInfoString));
    }
}

//********************************************************************************
// Parses a message into a group structure
//********************************************************************************
struct Group* parseMsg(char* msg)
{
	struct Group* newGroup = (struct Group*) malloc(sizeof(struct Group));

    // Get group name
    char* delimiterPosition = strchr(msg, ':');
    int length = delimiterPosition - msg;
    newGroup->name = strndup(msg, length);
    printf("l1=%d, l2=%d\n", strlen(msg), strlen(newGroup->name));
    newGroup->userInfoString = strndup(delimiterPosition+1, strrchr(msg, '#') - delimiterPosition);


    return newGroup;
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
    options->log_dev = "LOG";
    if (RVM_INIT(options) != RVM_SUCCESS)
    {
        fprintf(stderr, "RVM_INIT failed\n");
        exit(1);
    }

    // Set up the RDS allocator to manage the DATA file
    if (stat("DATA", &statbuf) == -1)
        perror("stat(DATA)");
    data_len.high = 0;
    data_len.low = statbuf.st_size;
    rds_load_heap("DATA", data_len, &static_area, &rc);
    if (rc != SUCCESS)
    {
        fprintf(stderr, "rds_load_heap returned %d\n", rc);
        exit(1);
    }

    return static_area;
}

//********************************************************************************
// Initializing permanent group structure
//********************************************************************************
struct Group* initRVMGroup()
{
    rvm_tid_t tid;
    rvm_init_tid(&tid);
    rvm_begin_transaction(&tid, restore);

    int rc;
    struct Group* theGroup = (struct Group*) rds_malloc(sizeof(struct Group), &tid, &rc);
    rvm_set_range(&tid, theGroup, sizeof(theGroup));

    rvm_end_transaction(&tid, flush);

    return theGroup;
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

