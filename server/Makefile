# Makefile for server -llwp -lseglwp 

LIBEVENT =      /usr/include/event2
LIBRVM =        /usr/include/rvm
CXXFLAGS =      -I$(LIBEVENT) -I$(LIBRVM) -Wall 
LIBS =          -levent -L/usr/lib -lrdslwp -lrvmlwp

all: rvmserv

rvmserv: rvmserver.c
	gcc $(CXXFLAGS) -g -o $@ rvmserver.c $(LIBS)

clean:
	rm -f rmserv *~


