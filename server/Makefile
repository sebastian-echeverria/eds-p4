# Makefile for server

LIBEVENT=       /usr/include/event2
CXXFLAGS =      -I$(LIBEVENT) -Wall
LIBS =          -levent

all: rvmserv

rvmserv: server.cpp
	c++ $(CXXFLAGS) -g -O2 -o $@ server.cpp $(LIBS)

clean:
	rm -f rmserv *~


