#!/bin/sh
faketime -f "$(ntpdate -q $1 | cut -d ' ' -f-3)" "$SHELL"
