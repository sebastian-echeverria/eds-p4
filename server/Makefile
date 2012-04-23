# Makefile for server -llwp -lseglwp 

LIBEVENT =      /usr/include/event2
LIBRVM =        /usr/include/rvm
CXXFLAGS =      -I$(LIBEVENT) -I$(LIBRVM) -Wall 
LIBS =          -levent -L/usr/lib -lrdslwp -lrvmlwp

all: rvmserv

rvmserv: server.cpp
	c++ $(CXXFLAGS) -g -o $@ server.cpp $(LIBS)

clean:
	rm -f rmserv *~


