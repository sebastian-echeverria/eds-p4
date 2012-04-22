/*
  This exmple program provides a trivial server program that listens for TCP
  connections on port 9995.  When they arrive, it prints the information to screen.

  Where possible, it exits cleanly in response to a SIGINT (ctrl-c).
*/

#include <string.h>
#include <errno.h>
#include <stdio.h>
#include <signal.h>
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

static const int PORT = 9995;

static void accept_conn_cb(struct evconnlistener *, evutil_socket_t,
                           struct sockaddr *, int socklen, void *);
static void read_cb(struct bufferevent *bev, void *ctx);
static void read_event_cb(struct bufferevent *bev, short events, void *ctx);
static void signal_cb(evutil_socket_t, short, void *);

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

    // Set callback for reading info, and set socket as read/write
    bufferevent_setcb(bev, read_cb, NULL, read_event_cb, NULL);
    bufferevent_enable(bev, EV_READ);
}

//********************************************************************************
// Event handler when there is data to be read
//********************************************************************************
static void read_cb(struct bufferevent *bev, void *ctx)
{
    // Copy data into an external buffer
    struct evbuffer *input = bufferevent_get_input(bev);
    char *record;
    ev_uint32_t record_len = evbuffer_get_length(input);
    evbuffer_remove(input, record, record_len);

    // Print what we received
    for(unsigned int i=0; i<record_len; i++)
    {
        putchar(record[i]);
    }
    putchar('\n');
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

