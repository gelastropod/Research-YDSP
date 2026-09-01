#!/usr/bin/env bash
set -e

for name in "$@"; do
	echo "----- Building and running $name: -----"
	make "build/$name"
	echo
	"./build/$name"
	echo
	echo
done
