
SRCS = $(wildcard *.md)

ALL: $(SRCS:.md=.html)

%.html: %.md
	python -m markdown $^ > $@
